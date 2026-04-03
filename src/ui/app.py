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

from src.config import FUNCTIONAL_TAGS, TAG_LABELS
from src.ui.components.query_box import render_query_box
from src.ui.components.db_browser import render_db_browser
from src.ui.components.e2e_wizard import render_e2e_wizard
from src.ui.components.config_translator import render_config_translator
from src.ui.components.rag_settings import init_rag_settings, render_rag_settings_panel
from src.ui.components.translation_quality import init_translation_quality, render_translation_quality_panel
from src.ui.components.data_ingest import render_data_ingest
from src.ui.components.auth import render_login_gate, render_user_badge

# Initialise RAG + Translation Quality session state defaults
init_rag_settings()
init_translation_quality()

# Ensure DB schema exists on every startup (idempotent — skips if tables already exist)
if "db_init_done" not in st.session_state:
    try:
        from src.database.connection import init_db
        init_db()
        st.session_state["db_init_done"] = True
    except Exception as _init_err:
        st.session_state["db_init_done"] = False
        st.session_state["db_init_error"] = str(_init_err)

# Login gate — stops rendering if login required and user is not authenticated
if not render_login_gate():
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
<div style="padding:10px 0 6px 0;">
  <div style="font-size:18px;font-weight:700;color:#7b2fff;letter-spacing:.5px;">⚡ Extreme Networks</div>
  <div style="font-size:15px;font-weight:600;color:#e6edf3;margin-top:2px;">CISCO ↔ EN CLI Mapping</div>
  <div style="font-size:12px;color:#8b949e;margin-top:2px;">Translate CLI commands across 6 network OSes</div>
</div>
""", unsafe_allow_html=True)
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
    except Exception as _db_err:
        st.warning(f"DB not connected: {_db_err}")

    # ── DB Completeness (admin/superadmin) ────────────────────────────────────
    from src.ui.components.auth import is_admin
    if is_admin():
        st.divider()
        try:
            from src.rag.quality import get_completeness_by_bin, DB_TARGET_ROWS
            bins = get_completeness_by_bin()
            total_rows = sum(b["row_count"] for b in bins)
            pct_total = round(100 * total_rows / DB_TARGET_ROWS, 1)
            st.markdown(f"**📊 DB Progress** — {total_rows:,} / {DB_TARGET_ROWS:,} rows")
            st.progress(total_rows / DB_TARGET_ROWS, text=f"{pct_total}% of 12K target")
            st.markdown("")
            for b in bins:
                short = b["tag"].strip("[]")
                fill = b["avg_fill_pct"]
                cnt = b["row_count"]
                st.markdown(
                    f"{b['status']} **{short}** &nbsp; {cnt} rows &nbsp; "
                    f"<span style='color:#8b949e'>{fill}% filled</span>",
                    unsafe_allow_html=True,
                )
        except Exception:
            pass  # DB not ready yet — silent

    st.divider()
    render_rag_settings_panel()
    st.divider()
    render_translation_quality_panel()
    st.divider()
    render_user_badge()
    st.caption("Powered by Claude claude-sonnet-4-6 + pgvector")

# ── BETA banner + copyright (all pages) ──────────────────────────────────────
st.markdown("""
<style>
@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.15; }
}
.beta-banner {
  background: linear-gradient(90deg, #1a1a2e 0%, #16213e 50%, #1a1a2e 100%);
  border: 1px solid #f85149;
  border-radius: 6px;
  padding: 8px 20px;
  text-align: center;
  margin-bottom: 6px;
}
.beta-text {
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 1.5px;
  animation: blink 1.6s ease-in-out infinite;
}
.copyright-bar {
  text-align: center;
  color: #8b949e;
  font-size: 11px;
  margin-top: 4px;
  margin-bottom: 12px;
}
</style>
<div class="beta-banner">
  <span class="beta-text">⚠ BETA &nbsp;·&nbsp; This application is under active development &nbsp;·&nbsp; For internal SE team use only &nbsp;·&nbsp; ⚠ BETA</span>
</div>
<div class="copyright-bar">
  © 2026 Khursheed Khan · Extreme Networks SA Team · CISCO ↔ EN CLI Mapping Agent · All rights reserved
</div>
""", unsafe_allow_html=True)

# ── Main content ──────────────────────────────────────────────────────────────
st.title("🔀 CISCO ↔ Extreme Networks CLI Mapping Agent")
st.markdown("*The New Rosetta Stone — Translate CLI commands across 6 network OSes | AI-powered E2E design*")

# Top-level tabs
tab_labels = [
    "🤖 AI Query",
    "⚙️ Config Translator",
    "🏗️ E2E Design Wizard",
    "🗄️ DB Browser",
    "📥 Add Data",
]
top_tabs = st.tabs(tab_labels)

with top_tabs[0]:
    render_query_box()

with top_tabs[1]:
    render_config_translator()

with top_tabs[2]:
    render_e2e_wizard()

with top_tabs[3]:
    render_db_browser()

with top_tabs[4]:
    render_data_ingest()
