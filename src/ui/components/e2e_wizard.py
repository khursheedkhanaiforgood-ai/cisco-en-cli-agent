"""
E2E Design Wizard — Lead Agent UI component.
Service-Based Architecture: user describes network intent → ordered CLI deployment script.
"""
import streamlit as st


GUARDRAIL_EXAMPLES = [
    "I want to design a campus network for 500 users across 3 floors with VOSS Fabric Engine core, OSPF routing, and 802.1X authentication. Generate the full CLI.",
    "Design a data center leaf-spine with Cisco NX-OS on spine and Extreme SLX-OS on leaf, VXLAN overlay, BGP underlay.",
    "I need to migrate 20 access switches from Cisco IOS to Extreme EXOS. Show me equivalent commands for VLANs, STP, and LLDP.",
    "Set up a small branch office with Cisco IOS-XE router, OSPF to HQ, VLAN segmentation for staff and guest, NTP and SNMP.",
    "Configure VOSS Zero Touch Fabric on 10 switches: auto-sense, I-SID assignment, SPBM, and BFD.",
]

INTENT_TIPS = """
**How to describe your intent for best results:**
- Include **scale**: number of switches / users / floors
- Specify **target OS(es)**: VOSS, EXOS, IOS-XE, NX-OS, or "all platforms"
- Name the **routing protocol**: OSPF, BGP, IS-IS, static
- State **security requirements**: 802.1X, TACACS+, ACLs, or none
- Mention **redundancy**: VRRP, HSRP, MLAG, DVR, or none
- List **key VLANs**: data, voice, management, IoT, guest
"""


def render_e2e_wizard():
    st.header("🏗️ E2E Network Design Wizard")
    st.markdown(
        "Describe your network design intent in plain English. "
        "The Lead Agent will break it into service phases and generate a complete, "
        "ordered CLI deployment script for your chosen platform(s)."
    )

    # Guardrail tips
    with st.expander("📋 How to write your design intent (click for tips)", expanded=False):
        st.markdown(INTENT_TIPS)

    st.divider()

    # Main intent input
    intent = st.text_area(
        "Describe your network design goal:",
        height=120,
        placeholder=GUARDRAIL_EXAMPLES[0],
        key="e2e_intent",
    )

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        os_filter = st.selectbox(
            "Target OS",
            ["All platforms", "cisco_ios", "cisco_iosxe", "cisco_nxos",
             "extreme_exos", "extreme_voss", "extreme_slxos"],
        )
    with col2:
        from src.config import FUNCTIONAL_TAGS, TAG_LABELS
        all_bins = [f"{TAG_LABELS[t]} {t}" for t in FUNCTIONAL_TAGS]
        selected_bins = st.multiselect(
            "Restrict to phases (optional)",
            options=all_bins,
            default=[],
            help="Leave empty to auto-detect from your intent",
        )
    with col3:
        st.write("")
        st.write("")
        run = st.button("🚀 Generate E2E Script", type="primary", use_container_width=True)

    # Example buttons
    st.markdown("**Quick-start examples:**")
    ex_cols = st.columns(len(GUARDRAIL_EXAMPLES))
    for i, ex in enumerate(GUARDRAIL_EXAMPLES):
        short = ex[:45] + "..."
        if ex_cols[i].button(short, key=f"e2e_ex_{i}", use_container_width=True):
            st.session_state["e2e_intent"] = ex
            st.rerun()

    if run and intent:
        _run_e2e(
            intent=intent,
            os_filter=None if os_filter == "All platforms" else os_filter,
            selected_bins=selected_bins,
        )
    elif run:
        st.warning("Please describe your network design intent first.")


def _run_e2e(intent: str, os_filter, selected_bins: list):
    from src.agents.e2e_deploy_agent import e2e_query, DEPLOY_ORDER
    from src.config import FUNCTIONAL_TAGS

    # Parse selected bins back to tags
    bins = None
    if selected_bins:
        bins = [tag for tag in FUNCTIONAL_TAGS if any(tag in s for s in selected_bins)]

    with st.spinner("Analyzing intent → querying 9 service bins → generating E2E script..."):
        try:
            result = e2e_query(
                intent=intent,
                os_filter=os_filter,
                bins=bins,
                top_k=5,
            )
        except Exception as e:
            st.error(f"E2E agent error: {e}")
            return

    # Status strip
    cols = st.columns(3)
    cols[0].success(f"**Phases used:** {len(result['bins_used'])}")
    cols[1].info(f"**DB results:** {sum(len(v.get('results', [])) for v in result['bin_results'].values())} mappings")
    cols[2].info(f"**Target:** {os_filter or 'All 6 platforms'}")

    st.divider()

    # E2E Script output
    st.subheader("📜 E2E CLI Deployment Script")
    st.markdown(result["e2e_script"])

    # Download
    st.download_button(
        "⬇️ Download CLI Script",
        data=result["e2e_script"],
        file_name="e2e_cli_deployment.md",
        mime="text/markdown",
    )

    # Guardrail follow-up questions
    if result.get("guardrail_questions"):
        st.divider()
        st.subheader("🔍 Refine Your Design — Follow-up Questions")
        for q in result["guardrail_questions"]:
            st.markdown(f"- {q}")
        st.info("Answer any of these in a new query above to get a more targeted deployment script.")

    # Per-bin details expander
    with st.expander("📊 Per-phase RAG details"):
        for tag, res in result["bin_results"].items():
            st.markdown(f"**{tag}** — {len(res.get('results', []))} mappings (similarity avg: "
                        f"{sum(r.get('similarity', 0) for r in res.get('results', [])) / max(len(res.get('results', [])), 1):.2f})")
