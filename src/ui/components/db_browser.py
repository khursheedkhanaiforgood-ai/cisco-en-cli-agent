"""DB Browser tab — full-text search, stats, and export."""
import streamlit as st
import pandas as pd


def render_db_browser():
    st.header("🗄️ Database Browser")

    try:
        from src.rag.search import get_stats
        stats = get_stats()
    except Exception as e:
        st.error(f"Cannot connect to database: {e}")
        st.code("python -m src.database.seed", language="bash")
        return

    # Stats row
    cols = st.columns(4)
    cols[0].metric("Total Mappings", stats["total"])
    cols[1].metric("Verified", stats["verified"])
    cols[2].metric("Embedded", stats["embedded"])
    cols[3].metric("Bins Populated", len([v for v in stats["by_tag"].values() if v > 0]))

    # Tag breakdown bar chart
    if stats["by_tag"]:
        st.subheader("Mappings per Functional Bin")
        tag_df = pd.DataFrame(
            [(tag, count) for tag, count in stats["by_tag"].items()],
            columns=["Tag", "Count"],
        ).sort_values("Count", ascending=False)
        st.bar_chart(tag_df.set_index("Tag"))

    st.divider()

    # Search
    st.subheader("Search All Mappings")
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        search = st.text_input("Search", placeholder="keyword or intent...", label_visibility="collapsed")
    with col2:
        from src.config import FUNCTIONAL_TAGS
        tag_filter = st.selectbox("Tag", ["All"] + FUNCTIONAL_TAGS, label_visibility="collapsed")
    with col3:
        limit = st.selectbox("Limit", [50, 100, 200, 500], label_visibility="collapsed")

    if search:
        from src.rag.search import keyword_search
        rows = keyword_search(
            search,
            tag_filter=None if tag_filter == "All" else tag_filter,
            limit=limit,
        )
    elif tag_filter != "All":
        from src.rag.search import get_all_by_tag
        rows = get_all_by_tag(tag_filter, limit=limit)
    else:
        rows = []
        st.info("Enter a search term or select a functional bin to browse mappings.")

    if rows:
        df = pd.DataFrame(rows)
        display_cols = [c for c in [
            "tag", "functional_intent",
            "cisco_ios", "cisco_iosxe", "cisco_nxos",
            "extreme_exos", "extreme_voss", "extreme_slxos",
            "negation_cisco", "negation_en",
            "notes", "source_ref", "confidence", "is_verified",
        ] if c in df.columns]

        st.markdown(f"**{len(df)} results**")
        st.dataframe(df[display_cols], use_container_width=True, height=500)

        csv_data = df[display_cols].to_csv(index=False)
        st.download_button(
            "⬇️ Export results as CSV",
            data=csv_data,
            file_name="cli_mappings_export.csv",
            mime="text/csv",
        )

    # Seed / admin section
    st.divider()
    st.subheader("⚙️ Database Administration")

    with st.expander("Seed & Initialize"):
        st.markdown("""
        **First-time setup:**
        ```bash
        # 1. Set your .env file
        cp .env.example .env && nano .env

        # 2. Initialize DB and load seed CSVs (~500 rows)
        python -m src.database.seed

        # 3. Optional: extract commands from PDFs (~3000+ more rows)
        python -m src.database.seed --pdf
        ```
        """)

    with st.expander("Re-seed / Overwrite"):
        st.warning("This will overwrite existing data.")
        if st.button("🔄 Re-seed from CSVs", type="secondary"):
            from src.database.seed import main as seed_main
            with st.spinner("Re-seeding..."):
                try:
                    seed_main(overwrite=True)
                    st.success("Seed complete. Refresh the page.")
                except Exception as e:
                    st.error(f"Seed failed: {e}")
