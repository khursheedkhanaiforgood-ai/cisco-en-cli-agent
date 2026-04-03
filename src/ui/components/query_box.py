"""AI Query tab — natural language query → Claude-formatted response."""
import streamlit as st
import time


def render_query_box():
    st.header("🤖 Natural Language CLI Query")
    st.markdown(
        "Ask anything about network configuration. The agent will find matching CLI commands "
        "across all 6 operating systems and explain the key differences."
    )

    # ── Team User Guide (collapsed by default so input is visible immediately)
    with st.expander("📖 Quick User Guide — Read Before You Start", expanded=False):
        st.markdown("""
> ✏️ *User guide content coming soon — Khursheed will provide the writeup.*
>
> **Placeholder structure (3 sections):**
>
> 🔹 **What this tool does**
> _(Brief description of the CLI Mapping Agent — purpose, scope, supported platforms)_
>
> 🔹 **How to use it**
> _(Step-by-step: ask a question → review cross-OS table → use E2E Wizard for full designs)_
>
> 🔹 **How to request new commands or report issues**
> _(Channel, contact, feedback process)_
        """)

    # ── Step instructions ─────────────────────────────────────────────────────
    st.markdown("""
<div style='display:flex;gap:12px;margin:14px 0 8px 0;flex-wrap:wrap;'>
  <div style='background:#1c1c35;border:1px solid #7b2fff;border-radius:6px;
              padding:8px 14px;font-size:13px;color:#c9d1d9;flex:1;min-width:160px;'>
    <span style='color:#a78bfa;font-weight:700;'>Step 1 &nbsp;💬</span><br>
    Type your CLI question in plain English
  </div>
  <div style='background:#1c2535;border:1px solid #3b82f6;border-radius:6px;
              padding:8px 14px;font-size:13px;color:#c9d1d9;flex:1;min-width:160px;'>
    <span style='color:#60a5fa;font-weight:700;'>Step 2 &nbsp;🖥</span><br>
    Optionally filter to one OS platform
  </div>
  <div style='background:#1c2520;border:1px solid #22c55e;border-radius:6px;
              padding:8px 14px;font-size:13px;color:#c9d1d9;flex:1;min-width:160px;'>
    <span style='color:#4ade80;font-weight:700;'>Step 3 &nbsp;🔍</span><br>
    Click <strong>Search</strong> — results appear below
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Query input row ───────────────────────────────────────────────────────
    st.markdown(
        "<div style='font-size:12px;color:#a78bfa;font-weight:600;"
        "margin-bottom:4px;'>▶ Your question</div>",
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns([5, 2, 2])
    with col1:
        user_query = st.text_input(
            "Your question",
            placeholder="e.g. How do I configure OSPF on a VLAN interface?",
            label_visibility="collapsed",
        )
    with col2:
        st.markdown(
            "<div style='font-size:12px;color:#60a5fa;font-weight:600;"
            "margin-bottom:4px;'>▼ OS filter (optional)</div>",
            unsafe_allow_html=True,
        )
        os_filter = st.selectbox(
            "OS filter",
            options=["All OSes", "cisco_ios", "cisco_iosxe", "cisco_nxos",
                     "extreme_exos", "extreme_voss", "extreme_slxos"],
            label_visibility="collapsed",
        )
    with col3:
        st.markdown("<div style='margin-top:22px;'></div>", unsafe_allow_html=True)
        run = st.button("🔍 Search", use_container_width=True, type="primary")

    # Tag override (advanced)
    with st.expander("Advanced: override functional bin"):
        from src.config import FUNCTIONAL_TAGS, TAG_LABELS
        tag_options = ["Auto-detect"] + FUNCTIONAL_TAGS
        tag_labels  = ["Auto-detect"] + [f"{TAG_LABELS[t]} {t}" for t in FUNCTIONAL_TAGS]
        tag_choice  = st.selectbox("Functional bin", tag_options, format_func=lambda x: tag_labels[tag_options.index(x)])

    if run and user_query:
        _run_query(
            query=user_query,
            os_filter=None if os_filter == "All OSes" else os_filter,
            tag_filter=None if tag_choice == "Auto-detect" else tag_choice,
        )
    elif run:
        st.warning("Please enter a question first.")

    # Sample queries
    st.divider()
    st.markdown("**Try these examples:**")
    examples = [
        "How do I configure OSPF area 0 on a VLAN interface?",
        "What is the command to set port speed and duplex on all platforms?",
        "How do I enable 802.1X authentication?",
        "Show me VLAN trunk configuration commands",
        "How do I set up BGP with a neighbor in VRF?",
        "What commands show system CPU and memory usage?",
        "How do I factory reset a switch?",
        "Configure NTP server on all platforms",
    ]
    cols = st.columns(4)
    for i, ex in enumerate(examples):
        if cols[i % 4].button(ex, key=f"ex_{i}", use_container_width=True):
            _run_query(query=ex, os_filter=None, tag_filter=None)


def _run_query(query: str, os_filter, tag_filter):
    from src.agents.orchestrator import query as agent_query
    from src.ui.components.rag_settings import get_rag_settings
    from src.ui.components.auth import get_current_user
    rag = get_rag_settings()
    current_user = get_current_user()
    username = current_user["username"] if current_user else "anonymous"

    with st.spinner("Searching database and generating response..."):
        start = time.time()
        try:
            result = agent_query(
                user_query=query,
                tag_filter=tag_filter,
                os_filter=os_filter,
                top_k=rag["rag_top_k"],
                threshold=rag["rag_threshold"],
                verified_only=rag["rag_verified_only"],
                min_confidence=rag["rag_min_confidence"],
                search_mode=rag["rag_search_mode"],
                username=username,
            )
        except Exception as e:
            st.error(f"Error: {e}")
            return

    elapsed = int((time.time() - start) * 1000)

    # Metadata strip
    col1, col2, col3 = st.columns(3)
    col1.info(f"**Bin:** {result.get('tag_used') or 'unclassified'}")
    col2.info(f"**Results:** {len(result.get('results', []))} mappings found")
    col3.info(f"**Time:** {elapsed}ms")

    st.divider()

    # AI Response
    st.markdown(result["ai_response"])

    # Raw results expander
    with st.expander("📊 Raw RAG results"):
        import pandas as pd
        rows = result.get("results", [])
        if rows:
            df = pd.DataFrame(rows)
            cols_to_show = [c for c in [
                "functional_intent", "tag", "similarity",
                "cisco_ios", "cisco_iosxe", "cisco_nxos",
                "extreme_exos", "extreme_voss", "extreme_slxos",
            ] if c in df.columns]
            st.dataframe(df[cols_to_show], use_container_width=True)
        else:
            st.info("No results found.")
