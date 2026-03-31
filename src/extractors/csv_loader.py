"""Load seed CSV files into the database with vector embeddings."""
import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.config import SEED_DIR, FUNCTIONAL_TAGS
from src.database.connection import get_session
from src.database.models import CLIMapping, ExtractionRun
from src.embeddings.encoder import encode_batch

logger = logging.getLogger(__name__)

CSV_FIELDS = [
    "tag", "functional_intent",
    "cisco_ios", "cisco_iosxe", "cisco_nxos",
    "extreme_exos", "extreme_voss", "extreme_slxos",
    "negation_cisco", "negation_en",
    "notes", "source_ref", "page_ref",
    "confidence", "is_verified",
]

SEED_FILES = {
    "[ONBOARD]":  "onboard.csv",
    "[SEC-ID]":   "sec_id.csv",
    "[SYS-INFO]": "sys_info.csv",
    "[IF-PHYS]":  "if_phys.csv",
    "[L2-SEG]":   "l2_seg.csv",
    "[FAB-SDN]":  "fab_sdn.csv",
    "[L3-VIRT]":  "l3_virt.csv",
    "[DIAG-LOG]": "diag_log.csv",
    "[MGMT-OPS]": "mgmt_ops.csv",
}


def load_all_seeds(overwrite: bool = False) -> dict:
    """Load all 9 seed CSV files into the database."""
    totals = {"added": 0, "skipped": 0, "errors": 0}
    for tag, filename in SEED_FILES.items():
        filepath = SEED_DIR / filename
        if not filepath.exists():
            logger.warning(f"Seed file not found: {filepath}")
            continue
        result = load_csv(filepath, tag, overwrite=overwrite)
        totals["added"] += result["added"]
        totals["skipped"] += result["skipped"]
        totals["errors"] += result["errors"]
        logger.info(f"  {tag}: +{result['added']} rows")
    return totals


def load_csv(filepath: Path, expected_tag: str, overwrite: bool = False) -> dict:
    """Load a single CSV file into the database."""
    run = ExtractionRun(
        source_type="csv",
        source_name=filepath.name,
        status="running",
    )

    rows_added = 0
    rows_skipped = 0
    errors = 0

    try:
        with get_session() as session:
            session.add(run)

        records = _parse_csv(filepath)
        logger.info(f"Parsed {len(records)} records from {filepath.name}")

        # Generate embeddings in batch
        intents = [r["functional_intent"] for r in records]
        logger.info(f"Generating embeddings for {len(intents)} records...")
        embeddings = encode_batch(intents)

        with get_session() as session:
            for record, embedding in zip(records, embeddings):
                try:
                    # Skip duplicates by intent + tag
                    if not overwrite:
                        from sqlalchemy import text
                        exists = session.execute(
                            text("SELECT 1 FROM cli_mappings WHERE tag = :tag "
                                 "AND functional_intent = :intent LIMIT 1"),
                            {"tag": record["tag"], "intent": record["functional_intent"]}
                        ).fetchone()
                        if exists:
                            rows_skipped += 1
                            continue

                    mapping = CLIMapping(
                        tag=record.get("tag", expected_tag),
                        functional_intent=record["functional_intent"],
                        cisco_ios=record.get("cisco_ios", ""),
                        cisco_iosxe=record.get("cisco_iosxe", ""),
                        cisco_nxos=record.get("cisco_nxos", ""),
                        extreme_exos=record.get("extreme_exos", ""),
                        extreme_voss=record.get("extreme_voss", ""),
                        extreme_slxos=record.get("extreme_slxos", ""),
                        negation_cisco=record.get("negation_cisco", ""),
                        negation_en=record.get("negation_en", ""),
                        notes=record.get("notes", ""),
                        source_ref=record.get("source_ref", ""),
                        page_ref=record.get("page_ref", ""),
                        confidence=float(record.get("confidence", 1.0)),
                        is_verified=str(record.get("is_verified", "false")).lower() == "true",
                        embedding=embedding,
                    )
                    session.add(mapping)
                    rows_added += 1
                except Exception as e:
                    logger.error(f"Error inserting row: {e}")
                    errors += 1

            # Update extraction run
            from sqlalchemy import text as sqlt
            session.execute(sqlt("""
                UPDATE extraction_runs
                SET rows_added = :added, rows_updated = :skipped,
                    completed_at = NOW(), status = 'completed'
                WHERE id = :id
            """), {"added": rows_added, "skipped": rows_skipped, "id": run.id})

    except Exception as e:
        logger.error(f"Failed to load {filepath.name}: {e}")
        errors += 1

    return {"added": rows_added, "skipped": rows_skipped, "errors": errors}


def _parse_csv(filepath: Path) -> list[dict]:
    """Parse CSV file into list of dicts, handling quoted fields."""
    records = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Clean whitespace from all values
            cleaned = {k.strip(): v.strip() for k, v in row.items() if k}
            if cleaned.get("functional_intent"):
                records.append(cleaned)
    return records
