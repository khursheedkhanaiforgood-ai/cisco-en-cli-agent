"""
E2E Deploy Agent — Lead Agent for Service-Based Architecture.

Takes a high-level network design intent and produces an ordered,
deployable CLI script by chaining all 9 functional bin sub-agents.

Usage:
    result = e2e_query("Design a 3-floor campus network with VOSS core, 802.1X, OSPF")
"""
import logging
from typing import Optional
import anthropic

from src.config import CLAUDE_MODEL, ANTHROPIC_API_KEY, FUNCTIONAL_TAGS, TAG_LABELS
from src.agents.orchestrator import query as bin_query

logger = logging.getLogger(__name__)

# ── Guardrail questions the agent uses to clarify intent ─────────────────────
CLARIFYING_QUESTIONS = [
    "What is the network scale? (number of users / access switches / distribution / core)",
    "Which core OS platform? (VOSS Fabric Engine / Cisco IOS-XE / NX-OS / mixed)",
    "Which routing protocol? (OSPF / BGP / static / VOSS IS-IS/SPBM)",
    "Is authentication required? (802.1X / TACACS+ / RADIUS / none)",
    "What redundancy model? (VRRP / HSRP / MLAG / VOSS DVR / none)",
    "Which VLANs/segments are needed? (e.g., data, voice, management, IoT)",
    "Generate CLI for which target OS(es)? (all 6 / Cisco only / Extreme only / specific)",
]

# Deployment order — the sequence in which bins should be configured
DEPLOY_ORDER = [
    "[ONBOARD]",   # 1. Factory reset, ZTP, hostnames
    "[IF-PHYS]",   # 2. Physical ports, LAG, PoE
    "[L2-SEG]",    # 3. VLANs, trunks, STP
    "[FAB-SDN]",   # 4. Fabric underlay (SPBM/IS-IS/VXLAN)
    "[L3-VIRT]",   # 5. IP, OSPF, BGP, VRRP, VRF
    "[SEC-ID]",    # 6. AAA, 802.1X, ACLs, SGT
    "[MGMT-OPS]",  # 7. NTP, SNMP, syslog, save
    "[DIAG-LOG]",  # 8. Verification commands
]

E2E_SYSTEM_PROMPT = """You are the Lead Network Design Agent for the CISCO-EN CLI Mapping system.

Your role is to take a high-level network design intent and:
1. Identify which functional service modules (bins) are needed
2. Ask clarifying questions if the intent is ambiguous
3. Produce an ordered, deployable CLI script organized by configuration phase
4. Flag platform-specific prerequisites (e.g., NX-OS 'feature' commands)
5. Mark each section clearly so a network engineer can deploy phase by phase

## Output Format
Always structure E2E output as:
### Phase 1 — Onboarding & Provisioning [ONBOARD]
<commands>

### Phase 2 — Physical Interfaces [IF-PHYS]
<commands>
... and so on through all required phases.

End with:
### Verification Commands
<show commands to confirm each phase>

## Rules
- Use exact CLI syntax from the database context provided
- If a command is not in the database, say "** Consult vendor docs for: <intent> **"
- Always show the OS label before each command block
- Highlight VOSS Zero Touch Fabric and NX-OS feature prerequisites explicitly
"""

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def e2e_query(
    intent: str,
    os_filter: Optional[str] = None,
    bins: Optional[list] = None,
    top_k: int = 5,
) -> dict:
    """
    Process a high-level network design intent end-to-end.

    Args:
        intent: Natural language design goal
        os_filter: Restrict to one OS column (None = all 6)
        bins: Which functional bins to include (None = auto-detect from intent)
        top_k: RAG results per bin

    Returns:
        {
            "intent": str,
            "bins_used": list[str],
            "bin_results": dict[str, dict],   # per-bin RAG results
            "e2e_script": str,                # final ordered CLI script
            "guardrail_questions": list[str], # follow-up prompts for user
        }
    """
    # 1. Detect which bins are relevant to this intent
    active_bins = bins or _detect_bins(intent)
    logger.info(f"E2E query — bins: {active_bins}")

    # 2. Query each bin in deployment order
    bin_results = {}
    for tag in DEPLOY_ORDER:
        if tag not in active_bins:
            continue
        try:
            result = bin_query(
                user_query=intent,
                tag_filter=tag,
                os_filter=os_filter,
                top_k=top_k,
            )
            if result.get("results"):
                bin_results[tag] = result
                logger.info(f"  {tag}: {len(result['results'])} results")
        except Exception as e:
            logger.error(f"  {tag} error: {e}")

    # 3. Build consolidated context for Claude
    context = _build_e2e_context(intent, bin_results, os_filter)

    # 4. Call Claude for E2E script
    try:
        client = _get_client()
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=E2E_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
        )
        e2e_script = message.content[0].text
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        e2e_script = _fallback_e2e_script(bin_results)

    # 5. Generate guardrail follow-up questions
    follow_ups = _suggest_followups(intent, active_bins)

    return {
        "intent": intent,
        "bins_used": active_bins,
        "bin_results": bin_results,
        "e2e_script": e2e_script,
        "guardrail_questions": follow_ups,
    }


def _detect_bins(intent: str) -> list:
    """Detect which functional bins are relevant to a design intent."""
    intent_lower = intent.lower()
    detected = []

    bin_signals = {
        "[ONBOARD]":  ["design", "deploy", "provision", "setup", "new", "install", "factory", "campus", "network"],
        "[IF-PHYS]":  ["port", "interface", "poe", "access point", "ap", "stack", "lag", "uplink", "speed"],
        "[L2-SEG]":   ["vlan", "segment", "trunk", "access", "voice vlan", "layer 2", "spanning", "loop"],
        "[FAB-SDN]":  ["fabric", "spbm", "vxlan", "underlay", "core", "spine", "leaf", "sd-access", "campus fabric"],
        "[L3-VIRT]":  ["routing", "ospf", "bgp", "route", "layer 3", "inter-vlan", "vrrp", "hsrp", "vrf", "ip"],
        "[SEC-ID]":   ["802.1x", "authentication", "radius", "tacacs", "security", "acl", "policy", "identity"],
        "[DIAG-LOG]": ["verify", "test", "check", "confirm", "validate", "troubleshoot", "ping", "trace"],
        "[MGMT-OPS]": ["manage", "ntp", "snmp", "syslog", "save", "backup", "monitor"],
    }

    for tag, signals in bin_signals.items():
        if any(s in intent_lower for s in signals):
            detected.append(tag)

    # Always include ONBOARD and MGMT-OPS for E2E designs
    for mandatory in ["[ONBOARD]", "[MGMT-OPS]"]:
        if mandatory not in detected:
            detected.append(mandatory)

    # Return in deployment order
    return [t for t in DEPLOY_ORDER if t in detected]


def _build_e2e_context(intent: str, bin_results: dict, os_filter: Optional[str]) -> str:
    """Build consolidated context message for Claude."""
    lines = [
        f"## Network Design Intent",
        f"{intent}",
        f"",
        f"## Target OS: {os_filter or 'All 6 platforms (IOS, IOS-XE, NX-OS, EXOS, VOSS, SLX-OS)'}",
        f"",
        f"## Retrieved CLI Commands by Service Phase",
        f"",
    ]

    for tag in DEPLOY_ORDER:
        if tag not in bin_results:
            continue
        label = TAG_LABELS.get(tag, tag)
        results = bin_results[tag].get("results", [])
        lines.append(f"### {tag} — {label}")
        for r in results[:5]:
            lines.append(f"  Intent: {r['functional_intent']}")
            for col in ["cisco_ios", "cisco_iosxe", "cisco_nxos", "extreme_exos", "extreme_voss", "extreme_slxos"]:
                if r.get(col):
                    lines.append(f"    {col}: {r[col]}")
            if r.get("notes"):
                lines.append(f"    Notes: {r['notes']}")
        lines.append("")

    lines.append("## Your Task")
    lines.append("Generate a complete, ordered E2E CLI deployment script for this network design.")
    lines.append("Organize by phase. Include verification commands at the end.")
    lines.append("Clearly label each OS. Flag NX-OS feature prerequisites and VOSS ZTF specifics.")

    return "\n".join(lines)


def _fallback_e2e_script(bin_results: dict) -> str:
    """Basic script without Claude when API is unavailable."""
    lines = ["# E2E CLI Deployment Script\n"]
    for tag in DEPLOY_ORDER:
        if tag not in bin_results:
            continue
        label = TAG_LABELS.get(tag, tag)
        lines.append(f"\n## Phase: {label} {tag}")
        for r in bin_results[tag].get("results", [])[:3]:
            lines.append(f"\n### {r['functional_intent']}")
            for col in ["cisco_ios", "cisco_iosxe", "cisco_nxos", "extreme_exos", "extreme_voss", "extreme_slxos"]:
                if r.get(col):
                    lines.append(f"  # {col}\n  {r[col]}")
    return "\n".join(lines)


def _suggest_followups(intent: str, active_bins: list) -> list:
    """Return relevant guardrail questions for the user."""
    questions = [CLARIFYING_QUESTIONS[0]]  # Always ask scale

    if "[FAB-SDN]" in active_bins or "fabric" in intent.lower() or "voss" in intent.lower():
        questions.append("For VOSS Fabric: how many NNI (uplink) ports per switch for auto-sense?")
    if "[L3-VIRT]" not in active_bins:
        questions.append(CLARIFYING_QUESTIONS[2])  # routing protocol
    if "[SEC-ID]" not in active_bins:
        questions.append(CLARIFYING_QUESTIONS[3])  # auth
    if "[L2-SEG]" in active_bins:
        questions.append(CLARIFYING_QUESTIONS[5])  # VLANs needed
    questions.append(CLARIFYING_QUESTIONS[6])  # target OS

    return questions[:5]
