"""DB completeness and quality metrics for the dashboard."""
from sqlalchemy import text

from src.database.connection import get_session
from src.config import FUNCTIONAL_TAGS, TAG_LABELS, OS_COLUMNS, OS_SHORT

DB_TARGET_ROWS = 12_000
BIN_TARGET_ROWS = DB_TARGET_ROWS // len(FUNCTIONAL_TAGS)  # ~1,333 per bin


def get_completeness_by_bin() -> list[dict]:
    """
    Per-bin completeness stats.

    Returns list of dicts (one per bin, all 9 always present):
        tag, label, row_count, avg_fill_pct, verified_count, status, bin_progress
    """
    sql = text("""
        SELECT
            tag,
            COUNT(*) AS row_count,
            ROUND(100.0 * AVG(
                (CASE WHEN cisco_ios     <> '' THEN 1 ELSE 0 END +
                 CASE WHEN cisco_iosxe   <> '' THEN 1 ELSE 0 END +
                 CASE WHEN cisco_nxos    <> '' THEN 1 ELSE 0 END +
                 CASE WHEN extreme_exos  <> '' THEN 1 ELSE 0 END +
                 CASE WHEN extreme_voss  <> '' THEN 1 ELSE 0 END +
                 CASE WHEN extreme_slxos <> '' THEN 1 ELSE 0 END
                )::float / 6
            ), 1) AS avg_fill_pct,
            COUNT(CASE WHEN is_verified THEN 1 END) AS verified_count
        FROM cli_mappings
        WHERE tag IS NOT NULL
        GROUP BY tag
        ORDER BY tag
    """)
    rows_by_tag = {}
    with get_session() as session:
        for row in session.execute(sql).fetchall():
            fill = float(row.avg_fill_pct or 0)
            rows_by_tag[row.tag] = {
                "tag": row.tag,
                "label": TAG_LABELS.get(row.tag, row.tag),
                "row_count": int(row.row_count),
                "avg_fill_pct": fill,
                "verified_count": int(row.verified_count),
                "status": "🟢" if fill >= 70 else ("🟡" if fill >= 40 else "🔴"),
                "bin_progress": min(1.0, int(row.row_count) / BIN_TARGET_ROWS),
            }

    # Ensure all 9 bins always appear, even if empty
    results = []
    for tag in FUNCTIONAL_TAGS:
        if tag in rows_by_tag:
            results.append(rows_by_tag[tag])
        else:
            results.append({
                "tag": tag,
                "label": TAG_LABELS.get(tag, tag),
                "row_count": 0,
                "avg_fill_pct": 0.0,
                "verified_count": 0,
                "status": "🔴",
                "bin_progress": 0.0,
            })
    return results


def get_completeness_2d(tag: str) -> dict:
    """
    2D completeness matrix for a specific bin.

    Returns:
        intents    — ordered list of functional_intent strings in this bin
        os_cols    — ordered list of OS column names
        matrix     — dict[intent][os_col] = True (filled) | False (empty)
        col_fill   — dict[os_col] = % fill rate (0-100)
        total_rows — number of rows in this bin
    """
    sql = text("""
        SELECT functional_intent,
               cisco_ios, cisco_iosxe, cisco_nxos,
               extreme_exos, extreme_voss, extreme_slxos
        FROM cli_mappings
        WHERE tag = :tag
        ORDER BY functional_intent
    """)
    with get_session() as session:
        rows = session.execute(sql, {"tag": tag}).fetchall()

    os_cols = ["cisco_ios", "cisco_iosxe", "cisco_nxos",
               "extreme_exos", "extreme_voss", "extreme_slxos"]

    intents = []
    matrix = {}
    col_totals = {col: 0 for col in os_cols}

    for row in rows:
        intent = row.functional_intent
        intents.append(intent)
        matrix[intent] = {}
        for col in os_cols:
            val = (getattr(row, col) or "").strip()
            has_data = bool(val)
            matrix[intent][col] = has_data
            if has_data:
                col_totals[col] += 1

    total = max(len(intents), 1)
    col_fill = {
        col: round(100 * col_totals[col] / total, 1)
        for col in os_cols
    }

    return {
        "tag": tag,
        "intents": intents,
        "os_cols": os_cols,
        "matrix": matrix,
        "col_fill": col_fill,
        "total_rows": len(intents),
    }


def get_os_fill_rates() -> dict[str, float]:
    """Overall fill rate per OS column across the entire DB."""
    sql = text("""
        SELECT
            ROUND(100.0 * COUNT(CASE WHEN cisco_ios     <> '' THEN 1 END) / NULLIF(COUNT(*),0), 1) AS cisco_ios,
            ROUND(100.0 * COUNT(CASE WHEN cisco_iosxe   <> '' THEN 1 END) / NULLIF(COUNT(*),0), 1) AS cisco_iosxe,
            ROUND(100.0 * COUNT(CASE WHEN cisco_nxos    <> '' THEN 1 END) / NULLIF(COUNT(*),0), 1) AS cisco_nxos,
            ROUND(100.0 * COUNT(CASE WHEN extreme_exos  <> '' THEN 1 END) / NULLIF(COUNT(*),0), 1) AS extreme_exos,
            ROUND(100.0 * COUNT(CASE WHEN extreme_voss  <> '' THEN 1 END) / NULLIF(COUNT(*),0), 1) AS extreme_voss,
            ROUND(100.0 * COUNT(CASE WHEN extreme_slxos <> '' THEN 1 END) / NULLIF(COUNT(*),0), 1) AS extreme_slxos
        FROM cli_mappings
    """)
    with get_session() as session:
        row = session.execute(sql).fetchone()
        return {col: float(getattr(row, col) or 0) for col in OS_COLUMNS}
