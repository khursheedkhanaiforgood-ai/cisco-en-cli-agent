"""
PDF command extractor — supports VOSS, EXOS, Cisco IOS/IOS-XE/NX-OS, SLX-OS.

Strategy:
- Uses pdfplumber for text + font metadata extraction
- Detects CLI commands by: monospace font, prompt patterns, verb patterns
- Maps section headings to functional tags via keyword classifier
- Deduplicates by tag + functional_intent before DB insert
"""
import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Prompt patterns per OS ────────────────────────────────────────────────────
_VOSS_PROMPTS = [
    r"^Switch(?::\d+)?[#>]\s+\S",           # Switch:1# command
    r"^Switch(?::\d+)?\(config[\w-]*\)#",    # Switch:1(config)#
    r"^\*[AB]:\w+[#>]",                       # *A:VSP9000#
    r"^VSP\S*[#>]\s+\S",                      # VSP9000#
]
_EXOS_PROMPTS = [
    r"^X\d{3}.*#\s+\S",                       # X440-8p# command
    r"^ExtremeXOS.*#",                         # ExtremeXOS>
    r"^\(Slot-\d\) \S+.*#",                   # (Slot-1) X460#
]
_CISCO_PROMPTS = [
    r"^\S+\(config[\w/-]*\)#",               # Router(config-if)#
    r"^Router[>#]\s+\S",                      # Router#
    r"^Switch[>#]\s+\S",                      # Switch>
    r"^N\d{4}[>#]\s+\S",                      # N9K-1#  (NX-OS)
    r"^\S+#\s+(show|conf|interface|ip|no)\s", # Generic privileged exec
]
_SLX_PROMPTS = [
    r"^SLX\S*[#>]\s+\S",
    r"^\S+\(config[\w-]*\)#",
]

_ALL_PROMPTS = _VOSS_PROMPTS + _EXOS_PROMPTS + _CISCO_PROMPTS + _SLX_PROMPTS

# ── Functional bin keywords ───────────────────────────────────────────────────
TAG_KEYWORDS = {
    "[ONBOARD]":  ["onboard", "zero touch", "ztp", "factory", "reset", "boot", "login",
                   "credential", "password", "provision", "auto-sense", "initial setup"],
    "[SEC-ID]":   ["security", "aaa", "authentication", "radius", "tacacs", "802.1x",
                   "dot1x", "policy", "acl", "access control", "trustsec", "sgt",
                   "eapol", "macsec", "arp inspection", "dhcp snoop", "port security"],
    "[SYS-INFO]": ["system", "version", "inventory", "hardware", "cpu", "memory",
                   "environment", "temperature", "power supply", "module", "slot",
                   "health", "alarm", "license", "show system", "show version"],
    "[IF-PHYS]":  ["interface", "port", "physical", "speed", "duplex", "poe",
                   "power over", "mirror", "mlag", "lag", "aggregat", "stack",
                   "channeliz", "jumbo", "breakout", "bandwidth", "port-channel"],
    "[L2-SEG]":   ["vlan", "layer 2", "spanning tree", "stp", "rstp", "mstp",
                   "lldp", "cdp", "fdb", "mac address", "trunk", "access port",
                   "private vlan", "eaps", "erps", "elrp", "loop protect", "dot1q"],
    "[FAB-SDN]":  ["fabric", "spbm", "isis", "i-sid", "vxlan", "lisp", "nve",
                   "fabric attach", "sd-access", "underlay", "overlay", "dvr",
                   "fabric connect", "auto-sense", "zero touch fabric", "evpn"],
    "[L3-VIRT]":  ["routing", "ospf", "bgp", "rip", "vrrp", "hsrp", "static route",
                   "ip route", "vrf", "vsn", "multicast", "pim", "igmp", "bfd",
                   "inter-vlan", "layer 3", "redistrib", "prefix-list"],
    "[DIAG-LOG]": ["troubleshoot", "debug", "ping", "traceroute", "trace",
                   "diagnostic", "log", "capture", "monitor", "l2trace",
                   "counters", "statistics", "errors", "tech-support", "packet capture"],
    "[MGMT-OPS]": ["management", "ntp", "snmp", "syslog", "backup", "restore",
                   "save", "tftp", "firmware", "upgrade", "banner", "telnet",
                   "ssh", "web", "gui", "rmon", "configuration management",
                   "copy", "archive", "reload"],
}

CLI_VERB_PATTERNS = re.compile(
    r"^(configure|show|enable|disable|create|delete|clear|copy|install|"
    r"tftp|ping|traceroute|debug|no |router |interface |vlan |spanning-tree|"
    r"ip |ipv6 |aaa |crypto |snmp|ntp |logging |boot |auto-sense|feature |"
    r"l2tracetree|unconfigure|save|reload|reboot|system |switchport |"
    r"network-policy|storm-control|channel-group|lacp|spanning|"
    r"redistribute|prefix-list|route-map|access-list|class-map|policy-map)",
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
        return "[MGMT-OPS]"
    return max(scores, key=scores.get)


# Section headings that indicate TOC/index pages — skip entirely
_SKIP_HEADINGS = re.compile(
    r"^(CONTEN\s*TS?|TABLE\s+OF\s+CONTENTS?|INDEX|PART\s*\d*|APPENDIX\s*\w*|"
    r"CHAPTER\s*\d+|PREFACE|GLOSSARY|NOTICES?|ABOUT\s+THIS|BEFORE\s+YOU|"
    r"REVISION\s+HISTORY|LEGAL\s+NOTICE|COPYRIGHT|TRADEMARKS?)$",
    re.IGNORECASE,
)

# Lines to reject as commands — help system noise, not real CLI
_BAD_COMMAND = re.compile(
    r"(\?|<tab>|\.\.\.more|%\s+(incomplete|invalid|ambiguous|error)|"
    r"^\s*%\s|^\s*#\s*$|^\s*-{3,}|^[A-Z\s]{1,4}$)",
    re.IGNORECASE,
)


def is_cli_command(line: str, is_monospace: bool = False) -> bool:
    """Determine if a text line is likely a CLI command."""
    line = line.strip()
    if not line or len(line) < 4:
        return False
    if _BAD_COMMAND.search(line):
        return False
    for pattern in _ALL_PROMPTS:
        if re.match(pattern, line):
            return True
    if is_monospace and CLI_VERB_PATTERNS.match(line):
        return True
    return False


def extract_from_pdf(
    pdf_path: Path,
    os_col: str,
    source_name: str = "",
    max_pages: int = 0,
) -> list[dict]:
    """
    Universal PDF extractor — works for any OS (VOSS, EXOS, Cisco IOS/XE/NX-OS, SLX-OS).

    Args:
        pdf_path:    Path to PDF file
        os_col:      Target OS column (e.g. "extreme_voss", "cisco_ios")
        source_name: Human-readable source name (defaults to filename)
        max_pages:   If > 0, limit to first N pages (for testing)

    Returns:
        List of extracted command records ready for approval/insert
    """
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed. Run: pip install pdfplumber")
        return []

    if not source_name:
        source_name = pdf_path.name

    logger.info(f"Extracting {os_col} commands from: {pdf_path.name}")
    records = []
    current_chapter = ""
    current_section = ""
    command_buffer = []

    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        total = len(pages)

        for page_num, page in enumerate(pages):
            if page_num % 50 == 0 and page_num > 0:
                logger.info(f"  Page {page_num}/{total} — {len(records)} records so far")

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
                    # Flush command buffer on new heading
                    if command_buffer and current_section:
                        record = _make_record(
                            section=current_section,
                            chapter=current_chapter,
                            commands=command_buffer,
                            os_col=os_col,
                            page=str(page_num + 1),
                            source=source_name,
                        )
                        if record:
                            records.append(record)
                    command_buffer = []

                    # Skip TOC/index/part headings — they produce garbage records
                    if _SKIP_HEADINGS.match(text.strip()):
                        current_section = ""
                        continue

                    if size > 16:
                        current_chapter = text
                    else:
                        current_section = text
                    continue

                # Collect CLI commands
                if is_mono or is_cli_command(text, is_mono):
                    clean = re.sub(r"^\S+[#>]\s*", "", text).strip()
                    if clean and len(clean) > 2:
                        command_buffer.append(clean)

        # Flush final buffer
        if command_buffer and current_section:
            record = _make_record(
                section=current_section,
                chapter=current_chapter,
                commands=command_buffer,
                os_col=os_col,
                page=str(total),
                source=source_name,
            )
            if record:
                records.append(record)

    logger.info(f"Extracted {len(records)} records from {source_name}")
    return records


def extract_from_cisco_cr_pdf(
    pdf_path: Path,
    os_col: str,
    source_name: str = "",
    max_pages: int = 0,
) -> list[dict]:
    """
    Extractor for Cisco Command Reference PDFs (IOS / IOS-XE / NX-OS).

    These PDFs have no monospace fonts. Structure per page:
      - Large heading (size > 14, Univers-CondensedBold) = command name
      - Times-Bold + Times-Italic tokens in Syntax section = command syntax
      - Section labels (Univers-CondensedBold, smaller) = "SyntaxDescription",
        "CommandDefault", "CommandModes", "Examples" etc.

    Strategy:
      1. Accumulate heading words at size > 14 → functional_intent
      2. After "SyntaxDescription" label → collect Bold+Italic tokens → syntax
      3. Stop on next section label → flush record
    """
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed.")
        return []

    if not source_name:
        source_name = pdf_path.name

    _SECTION_LABELS = {
        "SyntaxDescription", "CommandDefault", "CommandModes",
        "CommandHistory", "UsageGuidelines", "Examples",
        "RelatedCommands", "Contents", "Preface",
    }

    logger.info(f"Extracting Cisco CR ({os_col}) from: {pdf_path.name}")
    records = []
    seen_intents: set[str] = set()

    current_heading_words: list[str] = []
    current_syntax_tokens: list[str] = []
    in_syntax = False

    def _flush_record():
        nonlocal current_heading_words, current_syntax_tokens, in_syntax
        if current_heading_words and current_syntax_tokens:
            intent = " ".join(current_heading_words).strip()[:200]
            norm = intent.lower()
            if norm not in seen_intents and len(intent) > 2:
                seen_intents.add(norm)
                syntax = " ".join(current_syntax_tokens[:30])
                tag = classify_tag(intent)
                records.append({
                    "tag":               tag,
                    "functional_intent": intent,
                    "commands_text":     syntax,
                    os_col:              syntax,
                    "source_ref":        source_name,
                    "page_ref":          "",
                    "notes":             "",
                })
        current_heading_words = []
        current_syntax_tokens = []
        in_syntax = False

    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        total = len(pages)

        for page_num, page in enumerate(pages):
            if page_num % 200 == 0 and page_num > 0:
                logger.info(f"  Page {page_num}/{total} — {len(records)} records so far")

            words = page.extract_words(extra_attrs=["fontname", "size"])
            if not words:
                continue

            last_heading_y = -999  # track Y position to group same-line heading words

            for w in words:
                text = w.get("text", "").strip()
                font = w.get("fontname", "")
                size = float(w.get("size", 10))
                word_y = float(w.get("top", 0))

                if not text:
                    continue

                is_heading_font = "Univers" in font or "UniversCondensed" in font
                is_bold         = "Bold" in font or "Times-Bold" in font
                is_italic       = "Italic" in font or "Times-Italic" in font
                is_large        = size > 14

                # ── Large heading word = command name ──────────────────────
                if is_large and is_heading_font:
                    # Same horizontal line as previous heading word → append
                    if abs(word_y - last_heading_y) < 4 and current_heading_words:
                        current_heading_words.append(text)
                    else:
                        # New line → flush previous record, start fresh heading
                        if current_heading_words:
                            _flush_record()
                        current_heading_words = [text]
                    last_heading_y = word_y
                    continue

                # ── Section label (small Univers-CondensedBold) ────────────
                # Strip spaces from label to match set keys
                label_key = text.replace(" ", "")
                if is_heading_font and not is_large:
                    if label_key in _SECTION_LABELS:
                        in_syntax = (label_key == "SyntaxDescription")
                    continue

                # ── Syntax tokens (Bold or Italic, normal size) ────────────
                if in_syntax and (is_bold or is_italic) and size >= 9:
                    # Skip obvious noise
                    if text not in ("no", "default") or current_syntax_tokens:
                        current_syntax_tokens.append(text)

    _flush_record()
    logger.info(f"Extracted {len(records)} records from {source_name}")
    return records


def extract_from_extreme_cr_pdf(
    pdf_path: Path,
    os_col: str,
    source_name: str = "",
    max_pages: int = 0,
) -> list[dict]:
    """
    Extractor for Extreme Networks CLI Reference PDFs (Fabric Engine / VOSS).

    Format: Montserrat font throughout, no monospace.
      - Size 14  = command syntax words (one command per page)
      - Size 12  = section labels: Syntax, Command Parameters, Command Mode, Default
      - Size 10  = description text
      - Size 13  = bullet point parameters

    Strategy: collect size-14 words per page → one record per unique command.
    """
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed.")
        return []

    if not source_name:
        source_name = pdf_path.name

    logger.info(f"Extracting Extreme CR ({os_col}) from: {pdf_path.name}")
    records = []
    seen_intents: set[str] = set()

    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        total = len(pages)

        for page_num, page in enumerate(pages):
            if page_num % 200 == 0 and page_num > 0:
                logger.info(f"  Page {page_num}/{total} — {len(records)} records so far")

            words = page.extract_words(extra_attrs=["fontname", "size"])
            if not words:
                continue

            # Collect size-14 words (command syntax) in order
            cmd_words = [
                w["text"].strip() for w in words
                if abs(float(w.get("size", 0)) - 14.0) < 0.5
                and w.get("text", "").strip()
            ]
            if not cmd_words:
                continue

            command = " ".join(cmd_words)
            # Use first 1-3 words as base intent key to group sub-commands
            intent = command[:200]
            norm = intent.lower()

            if norm in seen_intents:
                continue
            seen_intents.add(norm)

            tag = classify_tag(intent)
            records.append({
                "tag":               tag,
                "functional_intent": intent,
                "commands_text":     command,
                os_col:              command,
                "source_ref":        source_name,
                "page_ref":          str(page_num + 1),
                "notes":             "",
            })

    logger.info(f"Extracted {len(records)} records from {source_name}")
    return records


def detect_pdf_format(pdf_path: Path, sample_pages: int = 20) -> str:
    """
    Sample the first N pages of a PDF and return the best extractor type:
      'cisco_cr_pdf'   — Cisco Command Reference (Univers-CondensedBold headings, no monospace)
      'extreme_cr_pdf' — Extreme CR (Montserrat-only, size-14 command syntax)
      'pdf'            — Generic (monospace / CourierNewPSMT) — works for EXOS UG, VOSS UG

    Callers can rely on the returned string as a `type` value in seed_bulk.SOURCES.
    """
    try:
        import pdfplumber
    except ImportError:
        return "pdf"

    font_counts: dict[str, int] = {}
    has_monospace = False
    has_univers = False
    has_montserrat = False

    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages[:sample_pages]
        for page in pages:
            words = page.extract_words(extra_attrs=["fontname", "size"])
            for w in words:
                fn = (w.get("fontname") or "").lower()
                font_counts[fn] = font_counts.get(fn, 0) + 1
                if _is_monospace_font(w.get("fontname", "")):
                    has_monospace = True
                if "univers" in fn and "condensed" in fn:
                    has_univers = True
                if "montserrat" in fn:
                    has_montserrat = True

    if has_univers:
        return "cisco_cr_pdf"
    if has_montserrat and not has_monospace:
        return "extreme_cr_pdf"
    return "pdf"


# Keep old names as aliases so existing seed.py code still works
def extract_from_voss_pdf(pdf_path: Path, output_path: Path, max_pages: int = 0) -> list[dict]:
    records = extract_from_pdf(pdf_path, os_col="extreme_voss",
                               source_name=pdf_path.name, max_pages=max_pages)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(records, f, indent=2)
    return records


def extract_from_exos_pdf(pdf_path: Path, output_path: Path, max_pages: int = 0) -> list[dict]:
    records = extract_from_pdf(pdf_path, os_col="extreme_exos",
                               source_name=pdf_path.name, max_pages=max_pages)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(records, f, indent=2)
    return records


def load_extracted_to_db(json_path: Path, os_col: str) -> dict:
    """
    UPSERT extracted records into the database.

    Matching logic (by normalized functional_intent):
      - Match found  → UPDATE the target os_col column on the existing row
      - No match     → INSERT new row with only the target os_col filled

    This allows building up the cross-OS matrix incrementally:
      upload Cisco IOS PDF  → fills cisco_ios on new/existing rows
      upload NX-OS PDF later → fills cisco_nxos on those same rows
    """
    from src.database.connection import get_session
    from src.database.models import CLIMapping
    from src.embeddings.encoder import encode_batch
    from sqlalchemy import text

    with open(json_path) as f:
        records = json.load(f)

    if not records:
        return {"added": 0, "merged": 0, "errors": 0}

    logger.info(f"Upserting {len(records)} extracted records ({os_col}) into DB...")

    # Load all existing intents → id map (lowercase for case-insensitive match)
    with get_session() as session:
        existing_rows = session.execute(
            text("SELECT id, LOWER(TRIM(functional_intent)) AS norm_intent FROM cli_mappings")
        ).fetchall()
    existing_map = {row.norm_intent: row.id for row in existing_rows}

    to_insert = []
    to_merge  = []  # (record, existing_id)

    for r in records:
        norm = r["functional_intent"].lower().strip()
        if norm in existing_map:
            to_merge.append((r, existing_map[norm]))
        else:
            to_insert.append(r)

    merged = 0
    added  = 0
    errors = 0

    # ── MERGE: UPDATE existing rows with the new OS column value ─────────────
    if to_merge:
        logger.info(f"Merging {os_col} into {len(to_merge)} existing rows...")
        with get_session() as session:
            for record, row_id in to_merge:
                try:
                    cmd = record.get("commands_text", "")
                    if cmd:
                        session.execute(
                            text(f"UPDATE cli_mappings SET {os_col} = :cmd "
                                 "WHERE id = :id AND ({os_col} IS NULL OR {os_col} = '')".format(
                                     os_col=os_col)),
                            {"cmd": cmd, "id": row_id},
                        )
                        merged += 1
                except Exception as e:
                    logger.warning(f"Merge error for id {row_id}: {e}")
                    errors += 1

    # ── INSERT: new rows not yet in the DB ────────────────────────────────────
    if to_insert:
        logger.info(f"Generating embeddings for {len(to_insert)} new records...")
        intents = [r["functional_intent"] for r in to_insert]
        embeddings = encode_batch(intents)

        with get_session() as session:
            for record, embedding in zip(to_insert, embeddings):
                try:
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
                except Exception as e:
                    logger.warning(f"Insert error: {e}")
                    errors += 1

    logger.info(f"Done — inserted {added} new, merged {merged} existing, {errors} errors.")
    return {"added": added, "merged": merged, "errors": errors}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_monospace_font(fontname: str) -> bool:
    mono_indicators = ["Courier", "Mono", "Console", "Code", "Fixed",
                       "Terminal", "Typewriter", "LucidaConsole", "Inconsolata",
                       "SourceCode", "DejaVuSansMono", "Anonymous"]
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
        if abs(y - current_y) < 3:
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

    # Deduplicate + reject noise commands
    seen = set()
    unique_cmds = []
    for cmd in commands:
        cmd = cmd.strip()
        if cmd in seen or len(cmd) < 4:
            continue
        if _BAD_COMMAND.search(cmd):
            continue
        seen.add(cmd)
        unique_cmds.append(cmd)
    if not unique_cmds:
        return None

    tag = classify_tag(section, chapter)
    functional_intent = section.strip()[:200]

    return {
        "tag": tag,
        "functional_intent": functional_intent,
        "commands_text": " | ".join(unique_cmds[:10]),
        os_col: " | ".join(unique_cmds[:10]),
        "source_ref": source,
        "page_ref": page,
        "notes": f"Chapter: {chapter[:100]}" if chapter else "",
    }
