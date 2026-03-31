"""
CISCO-EN CLI Mapping Agent — Streamlit UI
Main entry point. Renders 9 functional tabs + Query + DB Browser.
"""
import streamlit as st

st.set_page_config(
    page_title="CISCO ↔ EN CLI Mapping Agent",
    page_icon="🔀",
    layout="wide",
    initial_sidebar_state="expanded",
)

from src.config import FUNCTIONAL_TAGS, TAG_LABELS, TAG_DESCRIPTIONS
from src.ui.components.query_box import render_query_box
from src.ui.components.bin_tabs import render_bin_tab
from src.ui.components.db_browser import render_db_browser
from src.ui.components.e2e_wizard import render_e2e_wizard
from src.ui.components.rag_settings import init_rag_settings, render_rag_settings_panel
from src.ui.components.data_ingest import render_data_ingest

# Initialise RAG session state defaults
init_rag_settings()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Extreme_Networks_logo.svg/320px-Extreme_Networks_logo.svg.png", width=180)
    st.markdown("## CISCO ↔ EN CLI Mapping")
    st.markdown("*Translate CLI commands across 6 network OSes*")
    st.divider()

    st.markdown("### OS Coverage")
    st.markdown("""
    | Vendor | OS |
    |--------|-----|
    | Cisco | IOS classic |
    | Cisco | IOS-XE 17.x |
    | Cisco | NX-OS 10.x |
    | Extreme | ExtremeXOS 33.x |
    | Extreme | VOSS/FE 9.x |
    | Extreme | SLX-OS 20.x |
    """)
    st.divider()

    try:
        from src.rag.search import get_stats
        stats = get_stats()
        st.metric("Total Mappings", stats["total"])
        st.metric("Verified", stats["verified"])
        col1, col2 = st.columns(2)
        col1.metric("Embedded", stats["embedded"])
        col2.metric("Coverage", f"{int(stats['embedded']/max(stats['total'],1)*100)}%")
    except Exception:
        st.info("Database not connected")

    st.divider()
    render_rag_settings_panel()
    st.divider()
    st.caption("Powered by Claude claude-sonnet-4-6 + pgvector")

# ── Main content ──────────────────────────────────────────────────────────────
st.title("🔀 CISCO ↔ Extreme Networks CLI Mapping Agent")
st.markdown("*The New Rosetta Stone — Translate CLI commands across 6 network OSes | AI-powered E2E design*")

# Top-level tabs
tab_labels = (
    ["🤖 AI Query", "🏗️ E2E Design Wizard"]
    + [f"{TAG_LABELS[t]} {t}" for t in FUNCTIONAL_TAGS]
    + ["🗄️ DB Browser", "📥 Add Data"]
)
top_tabs = st.tabs(tab_labels)

# Tab 0 — AI Query
with top_tabs[0]:
    render_query_box()

# Tab 1 — E2E Design Wizard (Lead Agent / SBA)
with top_tabs[1]:
    render_e2e_wizard()

# Tabs 2-10 — Functional Bins
for i, tag in enumerate(FUNCTIONAL_TAGS):
    with top_tabs[i + 2]:
        render_bin_tab(tag)

# Tab 11 — DB Browser
with top_tabs[-2]:
    render_db_browser()

# Tab 12 — Add Data (upload + crawler approval)
with top_tabs[-1]:
    render_data_ingest()
