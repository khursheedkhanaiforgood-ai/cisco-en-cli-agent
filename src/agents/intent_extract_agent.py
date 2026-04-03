"""
Intent Extractor Agent — Sprint 14.

Reads a ParseResult and produces a structured list of ConfigIntent objects —
the functional goals the configuration is trying to achieve, independent of
the specific CLI syntax used to achieve them.

These intents are the "source of truth" against which the translated config
is later verified by intent_verify_agent.py.

Analogy: like a translator first identifying the meaning of a paragraph
before rendering it in the target language.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import anthropic

from src.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from src.parsers.cisco_config_parser import ParseResult

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """
You are a senior network engineer analysing a Cisco configuration to extract its functional intents.

Your job: read the config and identify WHAT the network is supposed to DO — not HOW the Cisco commands achieve it.

For each distinct network function you find, output a JSON object with these fields:
{
  "id": "I-001",
  "category": "<category>",
  "statement": "<plain-English description of the intent>",
  "evidence": ["<cisco command 1>", "<cisco command 2>", ...],
  "bin_tag": "<[BIN-TAG]>"
}

Categories and bin_tags:
- "L2-Segmentation"    → [L2-SEG]   (VLANs, trunks, access ports)
- "Edge-Port-Security" → [SEC-ID]   (portfast, bpduguard, port security)
- "L3-Routing"         → [L3-VIRT]  (ip routing, SVIs, static routes, OSPF, BGP)
- "DHCP-Service"       → [MGMT-OPS] (dhcp pools, excluded addresses)
- "Voice-Transport"    → [L2-SEG]   (voice vlan, QoS for voice)
- "Management-Access"  → [MGMT-OPS] (VTY, SSH, console, enable secret)
- "Network-Time"       → [MGMT-OPS] (NTP)
- "Monitoring"         → [MGMT-OPS] (SNMP, syslog, logging)
- "AAA-Security"       → [SEC-ID]   (aaa, radius, tacacs)
- "Port-Aggregation"   → [IF-PHYS]  (port-channel, LACP)
- "Quality-of-Service" → [MGMT-OPS] (QoS, policy-map, class-map)
- "Redundancy"         → [L3-VIRT]  (VRRP, HSRP, GLBP)

Rules:
- Be concise — the statement must be one sentence
- Evidence = the 1-3 Cisco commands most directly responsible for this intent
- Do not invent intents not present in the config
- Group related commands into one intent (e.g. all VLAN-related commands = one L2-Segmentation intent)
- Output a JSON array of intent objects. Nothing else — no prose, no explanation.
"""


@dataclass
class ConfigIntent:
    """One functional intent extracted from a Cisco configuration."""
    id: str
    category: str
    statement: str
    evidence: list[str]
    bin_tag: str
    confidence: float = 1.0   # set by verifier later


@dataclass
class IntentMap:
    """All intents extracted from a configuration."""
    intents: list[ConfigIntent]
    device_name: str
    raw_response: str = ""

    def by_category(self, category: str) -> list[ConfigIntent]:
        return [i for i in self.intents if i.category == category]

    def by_bin(self, bin_tag: str) -> list[ConfigIntent]:
        return [i for i in self.intents if i.bin_tag == bin_tag]

    def as_text(self) -> str:
        lines = []
        for intent in self.intents:
            lines.append(f"{intent.id} | {intent.category} | {intent.bin_tag}")
            lines.append(f"  Statement: {intent.statement}")
            lines.append(f"  Evidence:  {' / '.join(intent.evidence)}")
        return "\n".join(lines)


def extract_intents(
    parse_result: ParseResult,
    device_index: int = 0,
) -> IntentMap:
    """
    Extract functional intents from a parsed Cisco configuration.

    Args:
        parse_result:  Output from cisco_config_parser.parse_config()
        device_index:  Which device to extract from (default: 0 = first device)

    Returns:
        IntentMap containing all detected intents
    """
    if not parse_result.devices:
        return IntentMap(intents=[], device_name="unknown")

    device = parse_result.devices[min(device_index, len(parse_result.devices) - 1)]

    # Build a compact config text from the device's sections
    config_text = _build_compact_config(device.sections)

    if not config_text.strip():
        return IntentMap(intents=[], device_name=device.hostname)

    prompt = (
        f"Extract the functional intents from this Cisco configuration for device '{device.hostname}':\n\n"
        f"```\n{config_text}\n```\n\n"
        f"Output a JSON array of intent objects as specified."
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
        logger.error(f"Intent extraction failed for device '{device.hostname}': {e}")
        return IntentMap(intents=[], device_name=device.hostname, raw_response=str(e))

    intents = _parse_intent_response(raw)
    return IntentMap(
        intents=intents,
        device_name=device.hostname,
        raw_response=raw,
    )


def extract_all_intents(parse_result: ParseResult) -> list[IntentMap]:
    """Extract intents for all devices in the parse result."""
    maps = []
    for i in range(len(parse_result.devices)):
        maps.append(extract_intents(parse_result, device_index=i))
    return maps


def _build_compact_config(sections) -> str:
    """Build a compact config text from a list of sections."""
    lines = []
    for sec in sections:
        if sec.section_type in ("comment", "prose"):
            continue
        lines.append(sec.header)
        for cl in sec.body:
            lines.append(f" {cl.text}")
    return "\n".join(lines)


def _parse_intent_response(raw: str) -> list[ConfigIntent]:
    """Parse Claude's JSON response into ConfigIntent objects."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            l for l in lines
            if not l.startswith("```")
        ).strip()

    try:
        data = json.loads(text)
        if not isinstance(data, list):
            data = [data]
    except json.JSONDecodeError:
        # Try to find JSON array in the response
        import re
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                logger.warning("Could not parse intent JSON response")
                return []
        else:
            return []

    intents = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        intents.append(ConfigIntent(
            id=item.get("id", f"I-{i+1:03d}"),
            category=item.get("category", "Unknown"),
            statement=item.get("statement", ""),
            evidence=item.get("evidence", []),
            bin_tag=item.get("bin_tag", ""),
        ))
    return intents
