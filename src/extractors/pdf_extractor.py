"""
PDF command extractor for VOSS and ExtremeXOS user guides.

Strategy:
- Uses pdfplumber for text + font metadata extraction
- Detects CLI commands by: monospace font, prompt patterns, indented code blocks
- Maps section headings to functional tags via keyword classifier
- Outputs JSON intermediate files, then bulk-inserts to DB
"""
import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Prompt patterns that signal a CLI command line ────────────────────────────
CLI_PROMPT_PATTERNS = [
    r"^Switch(?::\d+)?[#>]\s+\S",          # VOSS: Switch:1# command
    r"^Switch(?::\d+)?\(config[\w-]*\)#",   # VOSS config mode
    r"^\*[AB]:\w+[#>]",                      # VOSS VSP prompt
    r"^X\d{3}.*#\s+\S",                      # EXOS: X440-8p#
    r"^\S+\(config[\w-]*\)#",               # Cisco config mode
    r"^Switch[>#]\s+\S",                     # Generic switch prompt
    r"^Router[>#]\s+\S",                     # Router prompt
]

# ── Keywords → tag mapping ────────────────────────────────────────────────────
TAG_KEYWORDS = {
    "[ONBOARD]":  ["onboard", "zero touch", "ztp", "factory", "reset", "boot", "login",
                   "credential", "password", "provision", "auto-sense", "initial"],
    "[SEC-ID]":   ["security", "aaa", "authentication", "radius", "tacacs", "802.1x",
                   "dot1x", "policy", "acl", "access control", "trustsec", "sgt",
                   "eapol", "mac-sec", "arp inspection", "dhcp snoop"],
    "[SYS-INFO]": ["system", "version", "inventory", "hardware", "cpu", "memory",
                   "environment", "temperature", "power supply", "module", "slot",
                   "health", "alarm", "license"],
    "[IF-PHYS]":  ["interface", "port", "physical", "speed", "duplex", "poe",
                   "power over", "mirror", "mlag", "lag", "aggregat", "stack",
                   "channeliz", "jumbo", "breakout"],
    "[L2-SEG]":   ["vlan", "layer 2", "spanning tree", "stp", "rstp", "mstp",
                   "lldp", "cdp", "fdb", "mac address", "trunk", "access port",
                   "private vlan", "eaps", "erps", "elrp", "loop"],
    "[FAB-SDN]":  ["fabric", "spbm", "isis", "i-sid", "vxlan", "lisp", "nve",
                   "fabric attach", "sd-access", "underlay", "overlay", "dvr",
                   "fabric connect", "auto-sense", "zero touch fabric"],
    "[L3-VIRT]":  ["routing", "ospf", "bgp", "rip", "vrrp", "hsrp", "static route",
                   "ip route", "vrf", "vsn", "multicast", "pim", "igmp", "bfd",
                   "inter-vlan", "layer 3"],
    "[DIAG-LOG]": ["troubleshoot", "debug", "ping", "traceroute", "trace",
                   "diagnostic", "log", "capture", "monitor", "l2trace",
                   "counters", "statistics", "errors", "tech-support"],
    "[MGMT-OPS]": ["management", "ntp", "snmp", "syslog", "backup", "restore",
                   "save", "tftp", "firmware", "upgrade", "banner", "telnet",
                   "ssh", "web", "gui", "rmon", "configuration management"],
}

CLI_VERB_PATTERNS = re.compile(
    r"^(configure|show|enable|disable|create|delete|clear|copy|install|"
    r"tftp|ping|traceroute|debug|no |router |interface |vlan |spanning-tree|"
    r"ip |ipv6 |aaa |crypto |snmp|ntp |logging |boot |auto-sense|"
    r"l2tracetree|unconfigure|save|reload|reboot|feature |system )",
    re.IGNORECASE
)


def classify_tag(section_title: str, chapter_title: str = "") -> str:
    """Classify a section into a functional tag using keyword matching."""
    text = (section_title + " " + chapter_title).lower()
    scores = {}
    for tag, keywords in TAG_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[tag] = score
    if not scores:
        return "[MGMT-OPS]"  # Default
    return max(scores, key=scores.get)


def is_cli_command(line: str, is_monospace: bool = False) -> bool:
    """Determine if a text line is likely a CLI command."""
    line = line.strip()
    if not line or len(line) < 3:
        return False
    # Check prompt patterns
    for pattern in CLI_PROMPT_PATTERNS:
        if re.match(pattern, line):
            return True
    # Check verb patterns (for monospace context)
    if is_monospace and CLI_VERB_PATTERNS.match(line):
        return True
    return False


def extract_from_voss_pdf(pdf_path: Path, output_path: Path, max_pages: int = 0) -> list[dict]:
    """
    Extract CLI commands from VOSS User Guide PDF.

    Args:
        pdf_path: Path to VOSS PDF
        output_path: Path to write intermediate JSON
        max_pages: If > 0, limit to first N pages (for testing)

    Returns:
        List of extracted command records
    """
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed. Run: pip install pdfplumber")
        return []

    logger.info(f"Extracting VOSS commands from: {pdf_path}")
    records = []
    current_chapter = ""
    current_section = ""
    command_buffer = []

    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        total = len(pages)

        for page_num, page in enumerate(pages):
            if page_num % 100 == 0:
                logger.info(f"  Processing page {page_num}/{total}...")

            words = page.extract_words(extra_attrs=["fontname", "size"])
            if not words:
                continue

            lines = _group_words_to_lines(words)

            for line_data in lines:
                text = line_data["text"].strip()
                font = line_data.get("fontname", "")
                size = line_data.get("size", 10)
                is_mono = _is_monospace_font(font)
                is_heading = size > 13 and not is_mono

                if not text:
                    continue

                # Flush command buffer when we hit a new section
                if is_heading:
                    if command_buffer and current_section:
                        record = _make_record(
                            section=current_section,
                            chapter=current_chapter,
                            commands=command_buffer,
                            os_col="extreme_voss",
                            page=str(page_num + 1),
                            source="VOSS-8.9-UG",
                        )
                        if record:
                            records.append(record)
                    command_buffer = []

                    # Update headings
                    if size > 16:
                        current_chapter = text
                    else:
                        current_section = text
                    continue

                # Collect CLI commands
                if is_mono or is_cli_command(text, is_mono):
                    # Strip prompts
                    clean = re.sub(r"^\S+[#>]\s*", "", text).strip()
                    if clean and len(clean) > 2:
                        command_buffer.append(clean)

        # Flush final buffer
        if command_buffer and current_section:
            record = _make_record(
                section=current_section,
                chapter=current_chapter,
                commands=command_buffer,
                os_col="extreme_voss",
                page=str(total),
                source="VOSS-8.9-UG",
            )
            if record:
                records.append(record)

    logger.info(f"Extracted {len(records)} records from VOSS PDF")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(records, f, indent=2)
    logger.info(f"Written to {output_path}")
    return records


def extract_from_exos_pdf(pdf_path: Path, output_path: Path, max_pages: int = 0) -> list[dict]:
    """Extract CLI commands from ExtremeXOS User Guide PDF."""
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed.")
        return []

    logger.info(f"Extracting EXOS commands from: {pdf_path}")
    records = []
    current_chapter = ""
    current_section = ""
    command_buffer = []

    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        total = len(pages)

        for page_num, page in enumerate(pages):
            if page_num % 100 == 0:
                logger.info(f"  Processing page {page_num}/{total}...")

            words = page.extract_words(extra_attrs=["fontname", "size"])
            if not words:
                continue

            lines = _group_words_to_lines(words)

            for line_data in lines:
                text = line_data["text"].strip()
                font = line_data.get("fontname", "")
                size = line_data.get("size", 10)
                is_mono = _is_monospace_font(font)
                is_heading = size > 13 and not is_mono

                if not text:
                    continue

                if is_heading:
                    if command_buffer and current_section:
                        record = _make_record(
                            section=current_section,
                            chapter=current_chapter,
                            commands=command_buffer,
                            os_col="extreme_exos",
                            page=str(page_num + 1),
                            source="EXOS-22.7-UG",
                        )
                        if record:
                            records.append(record)
                    command_buffer = []
                    if size > 16:
                        current_chapter = text
                    else:
                        current_section = text
                    continue

                # EXOS commands follow configure/show/enable/disable/create/delete pattern
                if is_mono or CLI_VERB_PATTERNS.match(text):
                    clean = re.sub(r"^\S+[#>]\s*", "", text).strip()
                    if clean and len(clean) > 2:
                        command_buffer.append(clean)

        if command_buffer and current_section:
            record = _make_record(
                section=current_section,
                chapter=current_chapter,
                commands=command_buffer,
                os_col="extreme_exos",
                page=str(total),
                source="EXOS-22.7-UG",
            )
            if record:
                records.append(record)

    logger.info(f"Extracted {len(records)} records from EXOS PDF")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(records, f, indent=2)
    logger.info(f"Written to {output_path}")
    return records


def load_extracted_to_db(json_path: Path, os_col: str) -> dict:
    """Load extracted JSON records into the database."""
    from src.database.connection import get_session
    from src.database.models import CLIMapping
    from src.embeddings.encoder import encode_batch

    with open(json_path) as f:
        records = json.load(f)

    logger.info(f"Loading {len(records)} extracted records ({os_col}) into DB...")
    intents = [r["functional_intent"] for r in records]
    embeddings = encode_batch(intents)

    added = 0
    with get_session() as session:
        for record, embedding in zip(records, embeddings):
            mapping = CLIMapping(
                tag=record["tag"],
                functional_intent=record["functional_intent"],
                **{os_col: record.get("commands_text", "")},
                notes=record.get("notes", ""),
                source_ref=record.get("source_ref", ""),
                page_ref=record.get("page_ref", ""),
                confidence=0.8,
                is_verified=False,
                embedding=embedding,
            )
            session.add(mapping)
            added += 1

    logger.info(f"Inserted {added} records.")
    return {"added": added}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_monospace_font(fontname: str) -> bool:
    mono_indicators = ["Courier", "Mono", "Console", "Code", "Fixed",
                       "Terminal", "Typewriter", "LucidaConsole"]
    return any(m.lower() in fontname.lower() for m in mono_indicators)


def _group_words_to_lines(words: list[dict]) -> list[dict]:
    """Group word objects into logical lines by vertical position."""
    if not words:
        return []
    lines = []
    current_line = [words[0]]
    current_y = words[0].get("top", 0)

    for word in words[1:]:
        y = word.get("top", 0)
        if abs(y - current_y) < 3:  # Same line (within 3pt)
            current_line.append(word)
        else:
            lines.append(_merge_line(current_line))
            current_line = [word]
            current_y = y
    if current_line:
        lines.append(_merge_line(current_line))
    return lines


def _merge_line(words: list[dict]) -> dict:
    """Merge word objects into a single line dict."""
    text = " ".join(w.get("text", "") for w in words)
    return {
        "text": text,
        "fontname": words[0].get("fontname", ""),
        "size": words[0].get("size", 10),
        "top": words[0].get("top", 0),
    }


def _make_record(
    section: str,
    chapter: str,
    commands: list[str],
    os_col: str,
    page: str,
    source: str,
) -> Optional[dict]:
    """Create a structured record from extracted data."""
    if not commands:
        return None
    # Deduplicate commands
    seen = set()
    unique_cmds = []
    for cmd in commands:
        if cmd not in seen and len(cmd) > 2:
            seen.add(cmd)
            unique_cmds.append(cmd)
    if not unique_cmds:
        return None

    tag = classify_tag(section, chapter)
    functional_intent = section.strip()
    if len(functional_intent) > 200:
        functional_intent = functional_intent[:200]

    return {
        "tag": tag,
        "functional_intent": functional_intent,
        "commands_text": " | ".join(unique_cmds[:10]),  # Max 10 commands per record
        "source_ref": source,
        "page_ref": page,
        "notes": f"Chapter: {chapter[:100]}" if chapter else "",
        os_col: " | ".join(unique_cmds[:10]),
    }
