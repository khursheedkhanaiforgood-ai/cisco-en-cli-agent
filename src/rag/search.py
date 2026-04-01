"""RAG semantic search over cli_mappings using pgvector cosine similarity."""
import logging
import time
from typing import Optional
from sqlalchemy import text

from src.database.connection import get_session
from src.database.models import CLIMapping, QueryLog
from src.embeddings.encoder import encode
from src.config import RAG_TOP_K, RAG_SIMILARITY_THRESHOLD, FUNCTIONAL_TAGS

logger = logging.getLogger(__name__)


def search(
    query: str,
    tag_filter: Optional[str] = None,
    os_filter: Optional[str] = None,
    limit: int = RAG_TOP_K,
    threshold: float = RAG_SIMILARITY_THRESHOLD,
    verified_only: bool = False,
    min_confidence: float = 0.0,
    search_mode: str = "Semantic (vector)",
    username: Optional[str] = None,
    source: str = "ai_query",
) -> list[dict]:
    """
    Semantic search over CLI mappings.

    Args:
        query: Natural language query (e.g. "create a vlan on trunk port")
        tag_filter: Optional functional bin tag (e.g. "[L2-SEG]")
        os_filter: Optional OS column name (e.g. "extreme_exos")
        limit: Max number of results
        threshold: Minimum cosine similarity (0-1)
        verified_only: If True, only return is_verified=True rows
        min_confidence: Minimum confidence score filter
        search_mode: "Semantic (vector)" | "Keyword (ILIKE)" | "Hybrid (semantic + keyword)"

    Returns:
        List of dicts with mapping data + similarity score
    """
    # Route to keyword search if mode requires it
    if "Keyword" in search_mode:
        return keyword_search(query, tag_filter=tag_filter, limit=limit,
                              min_confidence=min_confidence, verified_only=verified_only)
    if "Hybrid" in search_mode:
        sem = _semantic_search(query, tag_filter, os_filter, limit, threshold,
                               verified_only, min_confidence)
        kw  = keyword_search(query, tag_filter=tag_filter, limit=limit // 2,
                             min_confidence=min_confidence, verified_only=verified_only)
        # Merge deduped by id, semantic results first
        seen = {r["id"] for r in sem}
        return sem + [r for r in kw if r.get("id") not in seen]

    return _semantic_search(query, tag_filter, os_filter, limit, threshold,
                            verified_only, min_confidence, username=username, source=source)


def _semantic_search(
    query: str,
    tag_filter: Optional[str],
    os_filter: Optional[str],
    limit: int,
    threshold: float,
    verified_only: bool,
    min_confidence: float,
    username: Optional[str] = None,
    source: str = "ai_query",
) -> list[dict]:
    """Core pgvector cosine similarity search."""
    start_time = time.time()

    query_vector = encode(query)
    vector_str = "[" + ",".join(f"{v:.6f}" for v in query_vector) + "]"

    # Build WHERE clause
    conditions = [f"1 - (embedding <=> '{vector_str}'::vector) >= {threshold}"]
    if tag_filter and tag_filter in FUNCTIONAL_TAGS:
        conditions.append(f"tag = '{tag_filter}'")
    if os_filter:
        conditions.append(f"{os_filter} != ''")
    if verified_only:
        conditions.append("is_verified = true")
    if min_confidence > 0.0:
        conditions.append(f"confidence >= {min_confidence}")

    where_clause = " AND ".join(conditions)

    sql = text(f"""
        SELECT
            id, tag, functional_intent,
            cisco_ios, cisco_iosxe, cisco_nxos,
            extreme_exos, extreme_voss, extreme_slxos,
            negation_cisco, negation_en,
            notes, source_ref, page_ref,
            confidence, is_verified,
            1 - (embedding <=> '{vector_str}'::vector) AS similarity
        FROM cli_mappings
        WHERE {where_clause}
        ORDER BY embedding <=> '{vector_str}'::vector
        LIMIT :limit
    """)

    results = []
    with get_session() as session:
        rows = session.execute(sql, {"limit": limit}).fetchall()
        for row in rows:
            results.append({
                "id":               row.id,
                "tag":              row.tag,
                "functional_intent": row.functional_intent,
                "cisco_ios":        row.cisco_ios or "",
                "cisco_iosxe":      row.cisco_iosxe or "",
                "cisco_nxos":       row.cisco_nxos or "",
                "extreme_exos":     row.extreme_exos or "",
                "extreme_voss":     row.extreme_voss or "",
                "extreme_slxos":    row.extreme_slxos or "",
                "negation_cisco":   row.negation_cisco or "",
                "negation_en":      row.negation_en or "",
                "notes":            row.notes or "",
                "source_ref":       row.source_ref or "",
                "page_ref":         row.page_ref or "",
                "confidence":       row.confidence,
                "is_verified":      row.is_verified,
                "similarity":       round(float(row.similarity), 4),
            })

        # Log query
        elapsed_ms = int((time.time() - start_time) * 1000)
        top_sim = results[0]["similarity"] if results else 0.0
        log = QueryLog(
            query_text=query,
            tag_filter=tag_filter,
            os_filter=os_filter,
            results_count=len(results),
            top_similarity=top_sim,
            response_time_ms=elapsed_ms,
            username=username,
            source=source,
        )
        session.add(log)

    return results


def keyword_search(
    keyword: str,
    tag_filter: Optional[str] = None,
    limit: int = 50,
    min_confidence: float = 0.0,
    verified_only: bool = False,
) -> list[dict]:
    """Fuzzy keyword search using ILIKE (fallback / browse / keyword mode)."""
    conditions = [
        "(functional_intent ILIKE :kw OR cisco_ios ILIKE :kw OR cisco_iosxe ILIKE :kw "
        "OR extreme_exos ILIKE :kw OR extreme_voss ILIKE :kw OR extreme_slxos ILIKE :kw)"
    ]
    params = {"kw": f"%{keyword}%", "limit": limit}

    if tag_filter and tag_filter in FUNCTIONAL_TAGS:
        conditions.append("tag = :tag")
        params["tag"] = tag_filter
    if verified_only:
        conditions.append("is_verified = true")
    if min_confidence > 0.0:
        conditions.append(f"confidence >= {min_confidence}")

    where_clause = " AND ".join(conditions)
    sql = text(f"""
        SELECT id, tag, functional_intent,
               cisco_ios, cisco_iosxe, cisco_nxos,
               extreme_exos, extreme_voss, extreme_slxos,
               negation_cisco, negation_en,
               notes, source_ref, confidence, is_verified
        FROM cli_mappings
        WHERE {where_clause}
        ORDER BY tag, functional_intent
        LIMIT :limit
    """)

    results = []
    with get_session() as session:
        rows = session.execute(sql, params).fetchall()
        for row in rows:
            results.append({k: getattr(row, k, "") or "" for k in row._fields})
    return results


def get_all_by_tag(tag: str, limit: int = 500) -> list[dict]:
    """Return all rows for a given tag (for tab browsing)."""
    sql = text("""
        SELECT id, tag, functional_intent,
               cisco_ios, cisco_iosxe, cisco_nxos,
               extreme_exos, extreme_voss, extreme_slxos,
               negation_cisco, negation_en,
               notes, source_ref, page_ref, confidence, is_verified
        FROM cli_mappings
        WHERE tag = :tag
        ORDER BY functional_intent
        LIMIT :limit
    """)
    results = []
    with get_session() as session:
        rows = session.execute(sql, {"tag": tag, "limit": limit}).fetchall()
        for row in rows:
            results.append({k: getattr(row, k, "") or "" for k in row._fields})
    return results


def get_stats() -> dict:
    """Return database statistics for the UI dashboard."""
    sql = text("""
        SELECT
            COUNT(*) AS total,
            COUNT(CASE WHEN is_verified THEN 1 END) AS verified,
            COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) AS embedded
        FROM cli_mappings
    """)
    tag_sql = text("""
        SELECT tag, COUNT(*) AS cnt
        FROM cli_mappings
        GROUP BY tag
        ORDER BY tag
    """)
    with get_session() as session:
        row = session.execute(sql).fetchone()
        tag_rows = session.execute(tag_sql).fetchall()
        return {
            "total": row.total,
            "verified": row.verified,
            "embedded": row.embedded,
            "by_tag": {r.tag: r.cnt for r in tag_rows},
        }
