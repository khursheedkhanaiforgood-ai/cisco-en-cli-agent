"""
9 Functional Bin Sub-Agents.
Each wraps the orchestrator with a bin-specific system prompt and pre-set tag filter.
"""
from src.agents.orchestrator import query as base_query
from src.config import FUNCTIONAL_TAGS, TAG_LABELS, TAG_DESCRIPTIONS


def query_bin(tag: str, user_query: str, os_filter=None, top_k: int = 8) -> dict:
    """
    Query a specific functional bin sub-agent.
    Equivalent to calling the orchestrator with a forced tag_filter.
    """
    if tag not in FUNCTIONAL_TAGS:
        raise ValueError(f"Unknown tag: {tag}. Must be one of {FUNCTIONAL_TAGS}")

    return base_query(
        user_query=user_query,
        tag_filter=tag,
        os_filter=os_filter,
        top_k=top_k,
    )


# ── Convenience functions — one per bin ──────────────────────────────────────

def onboard(query: str, **kwargs) -> dict:
    return query_bin("[ONBOARD]", query, **kwargs)

def sec_id(query: str, **kwargs) -> dict:
    return query_bin("[SEC-ID]", query, **kwargs)

def sys_info(query: str, **kwargs) -> dict:
    return query_bin("[SYS-INFO]", query, **kwargs)

def if_phys(query: str, **kwargs) -> dict:
    return query_bin("[IF-PHYS]", query, **kwargs)

def l2_seg(query: str, **kwargs) -> dict:
    return query_bin("[L2-SEG]", query, **kwargs)

def fab_sdn(query: str, **kwargs) -> dict:
    return query_bin("[FAB-SDN]", query, **kwargs)

def l3_virt(query: str, **kwargs) -> dict:
    return query_bin("[L3-VIRT]", query, **kwargs)

def diag_log(query: str, **kwargs) -> dict:
    return query_bin("[DIAG-LOG]", query, **kwargs)

def mgmt_ops(query: str, **kwargs) -> dict:
    return query_bin("[MGMT-OPS]", query, **kwargs)


BIN_FUNCTIONS = {
    "[ONBOARD]":  onboard,
    "[SEC-ID]":   sec_id,
    "[SYS-INFO]": sys_info,
    "[IF-PHYS]":  if_phys,
    "[L2-SEG]":   l2_seg,
    "[FAB-SDN]":  fab_sdn,
    "[L3-VIRT]":  l3_virt,
    "[DIAG-LOG]": diag_log,
    "[MGMT-OPS]": mgmt_ops,
}
