"""
Master Orchestrator Agent.
Routes user queries to the RAG database and formats results via Claude.
"""
import logging
import time
from pathlib import Path
from typing import Optional

import anthropic

from src.config import CLAUDE_MODEL, ANTHROPIC_API_KEY, FUNCTIONAL_TAGS
from src.rag.search import search, get_stats

logger = logging.getLogger(__name__)

_client = None
_system_prompt = None
_bin_prompts: dict[str, str] = {}

# Map tag → bin prompt filename
_BIN_PROMPT_FILES = {
    "[ONBOARD]":  "bin_onboard.md",
    "[SEC-ID]":   "bin_sec_id.md",
    "[SYS-INFO]": "bin_sys_info.md",
    "[IF-PHYS]":  "bin_if_phys.md",
    "[L2-SEG]":   "bin_l2_seg.md",
    "[FAB-SDN]":  "bin_fab_sdn.md",
    "[L3-VIRT]":  "bin_l3_virt.md",
    "[DIAG-LOG]": "bin_diag_log.md",
    "[MGMT-OPS]": "bin_mgmt_ops.md",
}


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _get_system_prompt(tag: Optional[str] = None) -> str:
    global _system_prompt, _bin_prompts
    if _system_prompt is None:
        prompt_path = Path(__file__).parent / "prompts" / "system_master.md"
        _system_prompt = prompt_path.read_text()

    if tag and tag in _BIN_PROMPT_FILES:
        if tag not in _bin_prompts:
            bin_path = Path(__file__).parent / "prompts" / "bins" / _BIN_PROMPT_FILES[tag]
            try:
                _bin_prompts[tag] = bin_path.read_text()
            except FileNotFoundError:
                _bin_prompts[tag] = ""
        bin_guardrails = _bin_prompts.get(tag, "")
        if bin_guardrails:
            return _system_prompt + "\n\n---\n\n## Active Bin Guardrails\n\n" + bin_guardrails

    return _system_prompt


def classify_tag(query: str) -> Optional[str]:
    """Quick keyword-based tag classification before semantic search."""
    q = query.lower()
    tag_keywords = {
        "[ONBOARD]":  ["factory", "reset", "boot", "provision", "ztp", "initial", "login", "default"],
        "[SEC-ID]":   ["aaa", "radius", "tacacs", "802.1x", "dot1x", "acl", "access-list", "policy",
                       "sgt", "trustsec", "eapol", "authentication", "dhcp snoop", "arp inspect"],
        "[SYS-INFO]": ["version", "inventory", "hardware", "cpu", "memory", "uptime", "health", "alarm"],
        "[IF-PHYS]":  ["port", "interface", "speed", "duplex", "poe", "mirror", "lag", "lacp",
                       "mlag", "stack", "jumbo", "channeliz"],
        "[L2-SEG]":   ["vlan", "trunk", "access port", "stp", "spanning", "lldp", "cdp", "fdb",
                       "mac address", "eaps", "erps", "elrp", "pvlan", "private vlan"],
        "[FAB-SDN]":  ["fabric", "spbm", "isis", "i-sid", "vxlan", "lisp", "fabric attach",
                       "sd-access", "auto-sense", "zero touch", "dvr", "vsn"],
        "[L3-VIRT]":  ["ospf", "bgp", "rip", "vrrp", "hsrp", "route", "routing", "vrf",
                       "multicast", "pim", "igmp", "bfd", "ip address"],
        "[DIAG-LOG]": ["ping", "trace", "debug", "log", "troubleshoot", "capture", "error",
                       "counter", "statistic", "l2trace", "tech-support"],
        "[MGMT-OPS]": ["save", "backup", "restore", "ntp", "snmp", "syslog", "tftp", "firmware",
                       "upgrade", "banner", "telnet", "ssh", "web", "rmon"],
    }
    scores = {}
    for tag, keywords in tag_keywords.items():
        score = sum(1 for kw in keywords if kw in q)
        if score > 0:
            scores[tag] = score
    return max(scores, key=scores.get) if scores else None


def query(
    user_query: str,
    tag_filter: Optional[str] = None,
    os_filter: Optional[str] = None,
    top_k: int = 8,
    threshold: float = 0.35,
    verified_only: bool = False,
    min_confidence: float = 0.0,
    search_mode: str = "Semantic (vector)",
) -> dict:
    """
    Main entry point: process a user query end-to-end.

    Returns:
        {
            "query": str,
            "tag_used": str,
            "results": list[dict],   # RAG results
            "ai_response": str,       # Claude-formatted response
            "elapsed_ms": int,
        }
    """
    start = time.time()

    # 1. Auto-classify tag if not specified
    if not tag_filter:
        tag_filter = classify_tag(user_query)

    # 2. Semantic search — bin-scoped first
    results = search(
        query=user_query,
        tag_filter=tag_filter,
        os_filter=os_filter,
        limit=top_k,
        threshold=threshold,
        verified_only=verified_only,
        min_confidence=min_confidence,
        search_mode=search_mode,
    )

    # 2b. Fallback: if bin-scoped search returns nothing, search entire DB
    # This handles mis-tagged rows or edge cases where classify_tag picks the wrong bin.
    fallback_used = False
    if not results and tag_filter:
        logger.info(f"No results in bin '{tag_filter}' — falling back to full-DB search")
        results = search(
            query=user_query,
            tag_filter=None,          # drop bin filter — search all 9 bins
            os_filter=os_filter,
            limit=top_k,
            threshold=threshold,
            verified_only=verified_only,
            min_confidence=min_confidence,
            search_mode=search_mode,
        )
        fallback_used = bool(results)

    # 3. Build context for Claude
    context = _build_context(user_query, results, tag_filter, fallback_used=fallback_used)

    # 4. Call Claude for formatted response (inject bin guardrails if tag known)
    try:
        client = _get_client()
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=_get_system_prompt(tag=tag_filter),
            messages=[{"role": "user", "content": context}],
        )
        ai_response = message.content[0].text
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        ai_response = _fallback_response(results)

    elapsed_ms = int((time.time() - start) * 1000)

    return {
        "query":        user_query,
        "tag_used":     tag_filter,
        "fallback_used": fallback_used,
        "results":      results,
        "ai_response":  ai_response,
        "elapsed_ms":   elapsed_ms,
    }


def _build_context(query: str, results: list[dict], tag: Optional[str], fallback_used: bool = False) -> str:
    """Build the context message sent to Claude."""
    lines = [
        f"User query: {query}",
        f"Detected functional bin: {tag or 'unclassified'}",
    ]
    if fallback_used:
        lines.append(
            f"⚠️ Search scope: No results found in bin '{tag}' — results below are from a "
            f"FULL DATABASE fallback search across all bins. The command may be mis-tagged "
            f"in the database. Note the actual bin of each result in your response."
        )
    lines += ["", "Retrieved CLI mappings from database:", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"## Result {i} — {r['tag']} | {r['functional_intent']} (similarity: {r['similarity']})")
        lines.append(f"  Cisco IOS:      {r['cisco_ios'] or '—'}")
        lines.append(f"  Cisco IOS-XE:   {r['cisco_iosxe'] or '—'}")
        lines.append(f"  Cisco NX-OS:    {r['cisco_nxos'] or '—'}")
        lines.append(f"  Extreme EXOS:   {r['extreme_exos'] or '—'}")
        lines.append(f"  Extreme VOSS:   {r['extreme_voss'] or '—'}")
        lines.append(f"  Extreme SLX:    {r['extreme_slxos'] or '—'}")
        if r.get("negation_cisco"):
            lines.append(f"  Negate (Cisco): {r['negation_cisco']}")
        if r.get("negation_en"):
            lines.append(f"  Negate (EN):    {r['negation_en']}")
        if r.get("notes"):
            lines.append(f"  Notes:          {r['notes']}")
        lines.append("")

    lines.append("Please provide a clear, structured response with:")
    lines.append("1. A summary of the intent")
    lines.append("2. A markdown table comparing the commands across all 6 OSes")
    lines.append("3. Key platform differences and caveats")
    lines.append("4. Negation / undo forms")

    return "\n".join(lines)


def _fallback_response(results: list[dict]) -> str:
    """Generate a basic table response when Claude API is unavailable."""
    if not results:
        return "No matching CLI commands found in the database for this query."

    lines = ["## CLI Command Comparison\n"]
    headers = ["Intent", "IOS", "IOS-XE", "NX-OS", "EXOS", "VOSS", "SLX-OS"]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")

    for r in results:
        row = [
            r["functional_intent"][:40],
            r["cisco_ios"][:30] or "—",
            r["cisco_iosxe"][:30] or "—",
            r["cisco_nxos"][:30] or "—",
            r["extreme_exos"][:30] or "—",
            r["extreme_voss"][:30] or "—",
            r["extreme_slxos"][:30] or "—",
        ]
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)
