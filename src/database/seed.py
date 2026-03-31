"""
Master seed orchestrator.
Run this script to initialize the database and load all seed data.

Usage:
    python -m src.database.seed
    python -m src.database.seed --overwrite      # Re-load even if rows exist
    python -m src.database.seed --pdf            # Also extract from local PDFs
"""
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)


def main(overwrite: bool = False, extract_pdf: bool = False):
    logger.info("=" * 60)
    logger.info("  CISCO-EN CLI Mapping — Database Seed")
    logger.info("=" * 60)

    # 1. Initialize DB (run migrations)
    from src.database.connection import init_db
    logger.info("\n[1/3] Initializing database...")
    init_db()

    # 2. Load seed CSVs
    from src.extractors.csv_loader import load_all_seeds
    logger.info("\n[2/3] Loading seed CSVs...")
    result = load_all_seeds(overwrite=overwrite)
    logger.info(f"  Added: {result['added']}  Skipped: {result['skipped']}  Errors: {result['errors']}")

    # 3. Optional: Extract from PDFs
    if extract_pdf:
        logger.info("\n[3/3] Extracting from PDFs...")
        _extract_pdfs()
    else:
        logger.info("\n[3/3] PDF extraction skipped (use --pdf to enable)")

    # 4. Stats
    from src.rag.search import get_stats
    stats = get_stats()
    logger.info("\n" + "=" * 60)
    logger.info(f"  Total rows:    {stats['total']}")
    logger.info(f"  Embedded:      {stats['embedded']}")
    logger.info(f"  Verified:      {stats['verified']}")
    logger.info("\n  By tag:")
    for tag, cnt in stats["by_tag"].items():
        logger.info(f"    {tag:<15} {cnt:>5} rows")
    logger.info("=" * 60)
    logger.info("Seed complete.")


def _extract_pdfs():
    from src.config import BASE_DIR
    from src.extractors.pdf_extractor import (
        extract_from_voss_pdf, extract_from_exos_pdf, load_extracted_to_db
    )

    pdf_map = [
        (
            Path("/Users/khukhan/Downloads/VOSSUserGuide_8.9_UG.pdf"),
            BASE_DIR / "data/extracted/voss_commands.json",
            "extreme_voss",
            extract_from_voss_pdf,
        ),
        (
            Path("/Users/khukhan/Downloads/Extreme XOS User Guide 22.7.pdf"),
            BASE_DIR / "data/extracted/exos_commands.json",
            "extreme_exos",
            extract_from_exos_pdf,
        ),
    ]

    for pdf_path, out_path, os_col, extractor_fn in pdf_map:
        if not pdf_path.exists():
            logger.warning(f"PDF not found: {pdf_path}")
            continue
        logger.info(f"  Extracting {pdf_path.name}...")
        extractor_fn(pdf_path, out_path)
        if out_path.exists():
            result = load_extracted_to_db(out_path, os_col)
            logger.info(f"  Loaded {result['added']} records from {pdf_path.name}")


if __name__ == "__main__":
    overwrite = "--overwrite" in sys.argv
    extract_pdf = "--pdf" in sys.argv
    main(overwrite=overwrite, extract_pdf=extract_pdf)
