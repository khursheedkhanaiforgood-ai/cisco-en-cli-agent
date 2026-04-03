"""
Intent Verifier Agent — Sprint 14.

Compares the functional intents extracted from the original Cisco config
against the translated EXOS config to produce a confidence score per intent
and an overall blueprint confidence score.

This is the "translation quality" layer — operating at semantic/functional
level above syntax. Analogous to a professional translator verifying that
the meaning was preserved, not just the words.

Reference: Nida (1964) dynamic equivalence theory — a correct translation
preserves the effect and function of the original, not the literal form.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import anthropic

from src.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from src.agents.intent_extract_agent import ConfigIntent, IntentMap

logger = logging.getLogger(__name__)

# ── Calibration defaults ──────────────────────────────────────────────────────

DEFAULT_CALIBRATION = {
    "confidence_threshold": 70,      # % below which to flag as warning
    "strictness": "balanced",        # "strict" | "balanced" | "lenient"
    "category_weights": {            # relative importance per category
        "L2-Segmentation":    1.0,
        "L3-Routing":         1.2,
        "Edge-Port-Security": 1.0,
        "DHCP-Service":       0.9,
        "Voice-Transport":    0.8,
        "Management-Access":  0.7,
        "Network-Time":       0.5,
        "Monitoring":         0.5,
        "AAA-Security":       1.1,
        "Port-Aggregation":   0.9,
        "Quality-of-Service": 0.8,
        "Redundancy":         1.0,
    },
    "active_categories": [
        "L2-Segmentation", "L3-Routing", "Edge-Port-Security",
        "DHCP-Service", "Voice-Transport", "Management-Access",
        "AAA-Security",
    ],
}

_STRICTNESS_INSTRUCTIONS = {
    "strict": (
        "Judge strictly: the translated command must syntactically match a known "
        "verified EXOS command. Functional similarity alone is NOT enough. "
        "If the exact syntax is not present, reduce confidence."
    ),
    "balanced": (
        "Judge by functional equivalence: if the translated config achieves the same "
        "network function as the original intent, even using different syntax or mechanism, "
        "that counts as preserved. Minor syntax differences are acceptable."
    ),
    "lenient": (
        "Judge by topology/function preservation only: if the overall network behaviour "
        "(reachability, segmentation, routing) would be the same, count it as preserved. "
        "Ignore syntax differences and minor feature gaps."
    ),
}

_SYSTEM_PROMPT = """
You are a senior network engineer verifying that a Cisco → ExtremeXOS config translation preserved all intended network functions.

You will be given:
1. A list of intents extracted from the original Cisco config
2. The translated ExtremeXOS configuration

For each intent, score it 0–100:
- 90–100: Fully preserved — translated config clearly and completely achieves this intent
- 70–89:  Largely preserved — intent is achieved but with minor gaps or caveats
- 50–69:  Partially preserved — intent is partially addressed but key elements are missing
- 0–49:   Not preserved — intent is absent or incorrectly translated

Output a JSON array. One object per intent:
{
  "id": "<intent id>",
  "confidence": <0-100>,
  "status": "preserved" | "review" | "partial" | "failed",
  "note": "<one sentence explaining the score>"
}

Rules:
- Be honest — do not inflate scores
- If a CAVEAT marker appears in the translation for this intent, cap confidence at 80 unless the caveat has a complete workaround
- If a NO EQUIVALENT marker appears, set confidence to 0–30 and status "failed"
- Output only the JSON array — no prose
"""


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class IntentScore:
    """Verification score for one intent."""
    intent: ConfigIntent
    confidence: float        # 0–100
    status: str              # "preserved" | "review" | "partial" | "failed"
    note: str
    weight: float = 1.0      # from calibration


@dataclass
class VerificationResult:
    """Full verification result for one device translation."""
    device_name: str
    scores: list[IntentScore]
    overall_confidence: float
    calibration: dict
    pass_threshold: bool     # True if overall >= threshold
    raw_response: str = ""

    @property
    def preserved(self) -> list[IntentScore]:
        return [s for s in self.scores if s.status == "preserved"]

    @property
    def review_items(self) -> list[IntentScore]:
        return [s for s in self.scores if s.status == "review"]

    @property
    def failed_items(self) -> list[IntentScore]:
        return [s for s in self.scores if s.status in ("partial", "failed")]

    def summary_text(self) -> str:
        lines = [
            f"Overall Blueprint Confidence: {self.overall_confidence:.0f}%",
            f"Status: {'✅ PASS' if self.pass_threshold else '⚠ REVIEW REQUIRED'}",
            f"Threshold: {self.calibration['confidence_threshold']}%",
            "",
        ]
        for s in self.scores:
            icon = {"preserved": "✅", "review": "⚠", "partial": "⚠", "failed": "❌"}.get(s.status, "?")
            lines.append(
                f"{icon} [{s.intent.id}] {s.intent.category} — "
                f"{s.confidence:.0f}% — {s.note}"
            )
        return "\n".join(lines)


# ── Public API ────────────────────────────────────────────────────────────────

def verify_translation(
    intent_map: IntentMap,
    translated_script: str,
    target_version: str = "ExtremeXOS 33.x",
    calibration: Optional[dict] = None,
) -> VerificationResult:
    """
    Verify that the translated EXOS config preserves all intents from the original.

    Args:
        intent_map:         Output from intent_extract_agent.extract_intents()
        translated_script:  The full translated EXOS config text
        target_version:     Target OS version string (for display)
        calibration:        Calibration settings dict (uses DEFAULT_CALIBRATION if None)

    Returns:
        VerificationResult with per-intent scores and overall confidence
    """
    cal = {**DEFAULT_CALIBRATION, **(calibration or {})}
    active_cats = cal.get("active_categories", list(DEFAULT_CALIBRATION["active_categories"]))

    # Filter intents to active categories only
    active_intents = [
        i for i in intent_map.intents
        if i.category in active_cats
    ]

    if not active_intents:
        return VerificationResult(
            device_name=intent_map.device_name,
            scores=[],
            overall_confidence=100.0,
            calibration=cal,
            pass_threshold=True,
        )

    prompt = _build_verify_prompt(
        active_intents, translated_script, target_version, cal
    )

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text if message.content else "[]"
    except Exception as e:
        logger.error(f"Intent verification failed: {e}")
        raw = "[]"

    scores = _parse_scores(raw, active_intents, cal)
    overall = _weighted_confidence(scores, cal)
    threshold = cal.get("confidence_threshold", 70)

    return VerificationResult(
        device_name=intent_map.device_name,
        scores=scores,
        overall_confidence=overall,
        calibration=cal,
        pass_threshold=overall >= threshold,
        raw_response=raw,
    )


def _build_verify_prompt(
    intents: list[ConfigIntent],
    translated_script: str,
    target_version: str,
    cal: dict,
) -> str:
    strictness = cal.get("strictness", "balanced")
    strictness_instruction = _STRICTNESS_INSTRUCTIONS.get(
        strictness, _STRICTNESS_INSTRUCTIONS["balanced"]
    )

    intent_lines = []
    for intent in intents:
        intent_lines.append(
            f'{{"id": "{intent.id}", "category": "{intent.category}", '
            f'"statement": "{intent.statement}", '
            f'"evidence": {json.dumps(intent.evidence)}}}'
        )

    return (
        f"Strictness mode: {strictness.upper()}\n"
        f"Instruction: {strictness_instruction}\n\n"
        f"### Intents to verify ({len(intents)} total):\n"
        + "\n".join(intent_lines)
        + f"\n\n### Translated {target_version} configuration:\n"
        f"```\n{translated_script[:8000]}\n```\n\n"   # cap at 8K chars for prompt efficiency
        f"Score each intent. Output only the JSON array."
    )


def _parse_scores(
    raw: str,
    intents: list[ConfigIntent],
    cal: dict,
) -> list[IntentScore]:
    """Parse Claude's JSON scoring response into IntentScore objects."""
    text = raw.strip()
    # Strip markdown fences
    if text.startswith("```"):
        text = "\n".join(
            l for l in text.splitlines() if not l.startswith("```")
        ).strip()

    try:
        data = json.loads(text)
        if not isinstance(data, list):
            data = [data]
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                data = []
        else:
            data = []

    # Build id → score map
    score_map = {item.get("id"): item for item in data if isinstance(item, dict)}
    weights = cal.get("category_weights", DEFAULT_CALIBRATION["category_weights"])

    scores = []
    for intent in intents:
        item = score_map.get(intent.id, {})
        confidence = float(item.get("confidence", 50))
        status = item.get("status", "review")
        note = item.get("note", "Not evaluated")
        weight = weights.get(intent.category, 1.0)

        scores.append(IntentScore(
            intent=intent,
            confidence=confidence,
            status=status,
            note=note,
            weight=weight,
        ))

    return scores


def _weighted_confidence(scores: list[IntentScore], cal: dict) -> float:
    """
    Compute overall blueprint confidence as a weighted mean.

    confidence = Σ(weight_i × confidence_i) / Σ(weight_i)

    Reference: Shannon information fidelity — measures the ratio of
    preserved functional information to total functional information,
    weighted by category importance.
    """
    if not scores:
        return 100.0
    total_weight = sum(s.weight for s in scores)
    if total_weight == 0:
        return 100.0
    weighted_sum = sum(s.weight * s.confidence for s in scores)
    return round(weighted_sum / total_weight, 1)
