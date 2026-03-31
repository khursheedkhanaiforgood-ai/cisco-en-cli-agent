"""
RAG Tuning Panel — sidebar component.
Exposes calibration parameters with recommendations. Stores in st.session_state.
"""
import streamlit as st


# ── Defaults ─────────────────────────────────────────────────────────────────
DEFAULTS = {
    "rag_threshold":    0.35,
    "rag_top_k":        8,
    "rag_search_mode":  "Semantic (vector)",
    "rag_min_confidence": 0.0,
    "rag_verified_only": False,
}


def init_rag_settings():
    """Call once at app startup to initialise session state."""
    for k, v in DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v


def get_rag_settings() -> dict:
    """Return current RAG settings from session state."""
    return {k: st.session_state.get(k, v) for k, v in DEFAULTS.items()}


def render_rag_settings_panel():
    """Render the RAG tuning panel. Call inside st.sidebar or an expander."""
    st.markdown("### ⚙️ RAG Tuning")

    with st.expander("Calibration settings", expanded=False):

        # ── Similarity Threshold ────────────────────────────────────────────
        st.markdown("**Similarity Threshold**")
        st.caption(
            "Minimum cosine similarity for a DB result to be returned. "
            "Lower = more (but less relevant) results. CLI queries are terse, "
            "so 0.35 is intentionally low."
        )
        threshold = st.slider(
            "Threshold", min_value=0.10, max_value=0.90,
            value=st.session_state["rag_threshold"], step=0.05,
            key="rag_threshold",
            help="Recommended: 0.35 for short CLI queries · 0.45 for descriptive intent queries",
        )
        _threshold_advice(threshold)

        st.divider()

        # ── Top-K ───────────────────────────────────────────────────────────
        st.markdown("**Top-K Results**")
        st.caption("How many DB rows to send to Claude as context.")
        top_k = st.slider(
            "Top-K", min_value=3, max_value=20,
            value=st.session_state["rag_top_k"], step=1,
            key="rag_top_k",
            help="Recommended: 8 balanced · 3 focused single-command answers · 15 E2E designs",
        )
        _topk_advice(top_k)

        st.divider()

        # ── Search Mode ─────────────────────────────────────────────────────
        st.markdown("**Search Mode**")
        mode = st.radio(
            "Mode",
            ["Semantic (vector)", "Keyword (ILIKE)", "Hybrid (semantic + keyword)"],
            index=["Semantic (vector)", "Keyword (ILIKE)", "Hybrid (semantic + keyword)"].index(
                st.session_state.get("rag_search_mode", "Semantic (vector)")
            ),
            key="rag_search_mode",
            help="Semantic: best for intent queries · Keyword: best for exact CLI command lookup · Hybrid: broadest coverage",
        )
        _mode_advice(mode)

        st.divider()

        # ── Minimum Confidence ──────────────────────────────────────────────
        st.markdown("**Minimum Row Confidence**")
        st.caption(
            "Filter rows below this confidence score. "
            "1.0 = manually verified · 0.8 = PDF-extracted · 0.7 = web-crawled"
        )
        min_conf = st.slider(
            "Min confidence", min_value=0.0, max_value=1.0,
            value=st.session_state["rag_min_confidence"], step=0.1,
            key="rag_min_confidence",
            help="0.0 = include all · 0.8 = verified + PDF only · 1.0 = manually verified only",
        )
        if min_conf >= 0.9:
            st.info("Only manually-verified rows. Lowest coverage, highest accuracy.")
        elif min_conf >= 0.7:
            st.info("Excludes web-crawled rows. Good balance for production.")
        else:
            st.info("All rows included. Maximum coverage.")

        st.divider()

        # ── Verified Only ───────────────────────────────────────────────────
        st.checkbox(
            "Verified rows only",
            key="rag_verified_only",
            help="When checked, only rows with is_verified=True are returned. Safest for critical deployments.",
        )
        if st.session_state["rag_verified_only"]:
            st.warning("Verified-only mode: ~500 seed rows available. Turn off to access full DB.")

        st.divider()

        # ── Reset ───────────────────────────────────────────────────────────
        if st.button("↺ Reset to defaults", use_container_width=True):
            for k, v in DEFAULTS.items():
                st.session_state[k] = v
            st.rerun()

        # ── Summary ─────────────────────────────────────────────────────────
        st.caption(
            f"Current: threshold={threshold:.2f} · top_k={top_k} · "
            f"mode={mode.split(' ')[0]} · conf≥{min_conf:.1f}"
        )


def _threshold_advice(t: float):
    if t < 0.25:
        st.warning("Very low threshold — many irrelevant results may reach Claude.")
    elif t < 0.40:
        st.success("Recommended for terse CLI queries (e.g., 'show ospf neighbor')")
    elif t < 0.55:
        st.info("Good for descriptive intent queries (e.g., 'how do I configure OSPF?')")
    else:
        st.warning("High threshold — may miss relevant rows. Increase top-k to compensate.")


def _topk_advice(k: int):
    if k <= 4:
        st.info("Low top-k: fast, focused. Best for single-command lookups.")
    elif k <= 10:
        st.success("Recommended range for balanced context.")
    else:
        st.info("High top-k: comprehensive context for E2E design queries. Slower responses.")


def _mode_advice(mode: str):
    if "Semantic" in mode:
        st.success("Best for intent-based queries. Understands synonyms and context.")
    elif "Keyword" in mode:
        st.info("Best for exact CLI lookup (e.g., searching for 'spanning-tree portfast'). No semantic understanding.")
    else:
        st.info("Hybrid: runs both and merges results. Best coverage, slightly slower.")
