"""Functional bin tab — shows all mappings for a given tag in a filterable table."""
import streamlit as st
import pandas as pd

from src.config import TAG_LABELS, TAG_DESCRIPTIONS


def render_bin_tab(tag: str):
    label = TAG_LABELS.get(tag, tag)
    desc  = TAG_DESCRIPTIONS.get(tag, "")

    st.header(f"{label} — {tag}")
    st.markdown(desc)

    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input(
            "Filter by keyword",
            key=f"filter_{tag}",
            placeholder="e.g. ospf, vlan, port speed...",
        )
    with col2:
        os_col = st.selectbox(
            "Show OS",
            ["All", "cisco_ios", "cisco_iosxe", "cisco_nxos", "extreme_exos", "extreme_voss", "extreme_slxos"],
            key=f"os_{tag}",
        )

    try:
        from src.rag.search import get_all_by_tag, keyword_search
        if search_term:
            rows = keyword_search(search_term, tag_filter=tag, limit=200)
        else:
            rows = get_all_by_tag(tag, limit=500)
    except Exception as e:
        st.error(f"Database error: {e}")
        st.info("Make sure the database is seeded: `python -m src.database.seed`")
        return

    if not rows:
        st.info("No mappings found. Run `python -m src.database.seed` to load seed data.")
        return

    df = pd.DataFrame(rows)

    # Column selection
    base_cols = ["functional_intent"]
    if os_col == "All":
        os_cols = ["cisco_ios", "cisco_iosxe", "cisco_nxos", "extreme_exos", "extreme_voss", "extreme_slxos"]
    else:
        os_cols = [os_col]

    extra_cols = [c for c in ["negation_cisco", "negation_en", "notes"] if c in df.columns]
    display_cols = base_cols + [c for c in os_cols if c in df.columns] + extra_cols

    st.markdown(f"**{len(df)} mappings**")
    st.dataframe(
        df[display_cols],
        use_container_width=True,
        height=600,
        column_config={
            "functional_intent": st.column_config.TextColumn("Intent", width=250),
            "cisco_ios":        st.column_config.TextColumn("IOS", width=200),
            "cisco_iosxe":      st.column_config.TextColumn("IOS-XE", width=200),
            "cisco_nxos":       st.column_config.TextColumn("NX-OS", width=200),
            "extreme_exos":     st.column_config.TextColumn("EXOS", width=200),
            "extreme_voss":     st.column_config.TextColumn("VOSS", width=200),
            "extreme_slxos":    st.column_config.TextColumn("SLX-OS", width=200),
            "negation_cisco":   st.column_config.TextColumn("Undo (Cisco)", width=180),
            "negation_en":      st.column_config.TextColumn("Undo (EN)", width=180),
            "notes":            st.column_config.TextColumn("Notes", width=300),
        },
    )

    # Download button
    csv_data = df[display_cols].to_csv(index=False)
    st.download_button(
        label="⬇️ Download CSV",
        data=csv_data,
        file_name=f"{tag.strip('[]').lower()}_mappings.csv",
        mime="text/csv",
        key=f"dl_{tag}",
    )
