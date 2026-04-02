"""
Bulk seed script — processes local PDFs + web sources and upserts into DB.

Usage:
    python -m src.database.seed_bulk                         # uses DATABASE_URL from .env
    python -m src.database.seed_bulk --clean                 # delete non-seed rows first
    python -m src.database.seed_bulk --dry-run               # extract only, no DB insert
    DATABASE_URL="postgresql://..." python -m src.database.seed_bulk

Sources configured below in SOURCES list.
Intermediate JSON saved to data/extracted/bulk/ — safe to resume if interrupted.
"""
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# ── ensure src/ is importable when run as script ─────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SOURCE MANIFEST
# Edit this list to add/remove files. os_col = target DB column.
# ─────────────────────────────────────────────────────────────────────────────
DOWNLOADS = Path.home() / "Downloads"

SOURCES = [
    # ── GitHub cheat sheet (cisco_ios) ──────────────────────────────────────
    {
        "type":   "github_md",
        "url":    "https://raw.githubusercontent.com/r7perezyera/Cisco-IOS-Command-CheatSheets/master/README.md",
        "os_col": "cisco_ios",
        "name":   "cisco-ios-cheatsheet",
    },
    # ── Cisco IOS-XE 17.15 Command References (Cisco CR format) ─────────────
    {
        "type":   "cisco_cr_pdf",
        "path":   DOWNLOADS / "ipaddr-cr-book.pdf",
        "os_col": "cisco_iosxe",
        "name":   "ipaddr-cr-book",
    },
    {
        "type":   "cisco_cr_pdf",
        "path":   DOWNLOADS / "b_1715_programmability_cr.pdf",
        "os_col": "cisco_iosxe",
        "name":   "b_1715_programmability_cr",
    },
    {
        "type":   "cisco_cr_pdf",
        "path":   DOWNLOADS / "b_1715_9200_cr.pdf",
        "os_col": "cisco_iosxe",
        "name":   "b_1715_9200_cr",
    },
    {
        "type":   "cisco_cr_pdf",
        "path":   DOWNLOADS / "b_1715_9300_cr.pdf",
        "os_col": "cisco_iosxe",
        "name":   "b_1715_9300_cr",
    },
    {
        "type":   "cisco_cr_pdf",
        "path":   DOWNLOADS / "b_1715_9400_cr.pdf",
        "os_col": "cisco_iosxe",
        "name":   "b_1715_9400_cr",
    },
    {
        "type":   "cisco_cr_pdf",
        "path":   DOWNLOADS / "b_1715_9500_cr.pdf",
        "os_col": "cisco_iosxe",
        "name":   "b_1715_9500_cr",
    },
    {
        "type":   "cisco_cr_pdf",
        "path":   DOWNLOADS / "b_1715_9600_cr.pdf",
        "os_col": "cisco_iosxe",
        "name":   "b_1715_9600_cr",
    },
]

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "extracted" / "bulk"


# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean",   action="store_true", help="Delete non-seed rows before seeding")
    parser.add_argument("--dry-run", action="store_true", help="Extract only — do not insert into DB")
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if args.clean and not args.dry_run:
        _clean_non_seed_rows()

    total_added   = 0
    total_merged  = 0
    total_errors  = 0
    grand_records = 0

    for i, source in enumerate(SOURCES, 1):
        name   = source["name"]
        os_col = source["os_col"]
        logger.info(f"[{i}/{len(SOURCES)}] ── {name} ({os_col}) ──────────────────")

        cache_file = CACHE_DIR / f"{name}.json"

        # ── Extract (or load from cache) ──────────────────────────────────
        if cache_file.exists():
            logger.info(f"  Cache hit — loading {cache_file.name}")
            with open(cache_file) as f:
                records = json.load(f)
        else:
            records = _extract(source)
            if records is None:
                logger.warning(f"  Skipping {name} — extraction failed")
                continue
            with open(cache_file, "w") as f:
                json.dump(records, f, indent=2)
            logger.info(f"  Cached {len(records)} records → {cache_file.name}")

        logger.info(f"  {len(records)} records extracted")
        grand_records += len(records)

        if args.dry_run:
            logger.info("  [dry-run] skipping DB insert")
            continue

        # ── UPSERT into DB ────────────────────────────────────────────────
        result = _upsert(records, os_col, name)
        total_added  += result["added"]
        total_merged += result["merged"]
        total_errors += result.get("errors", 0)
        logger.info(
            f"  ✅ inserted {result['added']} new | "
            f"↗ merged {result['merged']} existing | "
            f"errors {result.get('errors', 0)}"
        )

    logger.info("=" * 60)
    logger.info(f"TOTAL RECORDS EXTRACTED : {grand_records:,}")
    if not args.dry_run:
        logger.info(f"INSERTED (new rows)     : {total_added:,}")
        logger.info(f"MERGED   (OS col filled): {total_merged:,}")
        logger.info(f"ERRORS                  : {total_errors:,}")
    logger.info("Done.")


# ─────────────────────────────────────────────────────────────────────────────

def _extract(source: dict) -> list[dict] | None:
    t = source["type"]
    if t == "cisco_cr_pdf":
        return _extract_cisco_cr(source)
    elif t == "pdf":
        return _extract_pdf(source)
    elif t == "github_md":
        return _extract_github_md(source)
    return None


def _extract_cisco_cr(source: dict) -> list[dict] | None:
    from src.extractors.pdf_extractor import extract_from_cisco_cr_pdf
    path = Path(source["path"])
    if not path.exists():
        logger.warning(f"  File not found: {path}")
        return None
    t0 = time.time()
    records = extract_from_cisco_cr_pdf(
        path, os_col=source["os_col"], source_name=source["name"]
    )
    logger.info(f"  Extracted in {int(time.time()-t0)}s")
    return records


def _extract_pdf(source: dict) -> list[dict] | None:
    from src.extractors.pdf_extractor import extract_from_pdf
    path = Path(source["path"])
    if not path.exists():
        logger.warning(f"  File not found: {path}")
        return None
    t0 = time.time()
    records = extract_from_pdf(path, os_col=source["os_col"], source_name=source["name"])
    logger.info(f"  Extracted in {int(time.time()-t0)}s")
    return records


def _extract_github_md(source: dict) -> list[dict] | None:
    """Fetch a GitHub raw markdown file and extract CLI commands by section."""
    import re
    try:
        import httpx
    except ImportError:
        logger.error("httpx not installed")
        return None

    from src.extractors.pdf_extractor import classify_tag, _BAD_COMMAND

    url    = source["url"]
    os_col = source["os_col"]
    name   = source["name"]

    try:
        resp = httpx.get(url, timeout=30, follow_redirects=True,
                         headers={"User-Agent": "CLI-Mapping-Bot/1.0"})
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"  Failed to fetch {url}: {e}")
        return None

    records      = []
    seen_intents: set[str] = set()
    current_heading = "General Cisco IOS Commands"
    current_commands: list[str] = []
    in_code_block = False

    for line in resp.text.splitlines():
        # Toggle code block
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        # Markdown heading → flush + new section
        if line.startswith("#") and not in_code_block:
            if current_commands:
                _flush(current_heading, current_commands, os_col, name,
                       records, seen_intents)
                current_commands = []
            current_heading = line.lstrip("#").strip()
            continue

        # Collect commands from code blocks or lines with Cisco patterns
        clean = re.sub(r"^\S+[#>$]\s*", "", line.strip()).strip()
        if not clean or len(clean) < 4:
            continue
        if _BAD_COMMAND.search(clean):
            continue
        # Accept if inside code block OR matches a known Cisco verb
        cisco_verbs = re.compile(
            r"^(show|no |ip |ipv6 |interface|router |vlan |spanning|"
            r"switchport|channel-group|access-list|route-map|crypto|"
            r"aaa |ntp |snmp|logging|enable|disable|shutdown|duplex|speed|"
            r"bandwidth|description|hostname|line |username|service|"
            r"clock|ntp|cdp|lldp|mpls|bgp|ospf|eigrp|rip)",
            re.IGNORECASE
        )
        if in_code_block or cisco_verbs.match(clean):
            current_commands.append(clean)

    if current_commands:
        _flush(current_heading, current_commands, os_col, name, records, seen_intents)

    return records


def _flush(heading, commands, os_col, source_name, records, seen_intents):
    from src.extractors.pdf_extractor import classify_tag, _BAD_COMMAND
    unique = list(dict.fromkeys(
        c for c in commands if len(c) > 3 and not _BAD_COMMAND.search(c)
    ))
    if not unique:
        return
    intent = heading.strip()[:200]
    if intent.lower() in seen_intents:
        return
    seen_intents.add(intent.lower())
    records.append({
        "tag":              classify_tag(intent),
        "functional_intent": intent,
        "commands_text":    " | ".join(unique[:10]),
        os_col:             " | ".join(unique[:10]),
        "source_ref":       source_name,
        "page_ref":         "",
        "notes":            "",
    })


def _upsert(records: list[dict], os_col: str, source_name: str) -> dict:
    """Write records to a temp JSON and call load_extracted_to_db."""
    import tempfile
    from src.extractors.pdf_extractor import load_extracted_to_db

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        json.dump(records, tmp)
        tmp_path = Path(tmp.name)
    try:
        return load_extracted_to_db(tmp_path, os_col)
    finally:
        tmp_path.unlink(missing_ok=True)


def _clean_non_seed_rows():
    from src.database.connection import get_session
    from sqlalchemy import text
    logger.info("Cleaning non-seed rows from DB...")
    with get_session() as session:
        result = session.execute(text(
            "DELETE FROM cli_mappings "
            "WHERE source_ref IS NOT NULL "
            "AND source_ref != 'seed' "
            "AND source_ref != '' "
            "AND source_ref NOT LIKE 'CSV%'"
        ))
    logger.info(f"Deleted non-seed rows.")


if __name__ == "__main__":
    main()
