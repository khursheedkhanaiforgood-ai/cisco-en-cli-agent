"""DB Browser tab — full-text search, stats, completeness dashboard, and export."""
import streamlit as st
import pandas as pd


def _render_completeness_dashboard(stats: dict):
    """Landing overview: one row per bin + 12K progress."""
    from src.rag.quality import get_completeness_by_bin, get_os_fill_rates, DB_TARGET_ROWS, BIN_TARGET_ROWS
    from src.config import TAG_LABELS, OS_SHORT

    st.subheader("📊 DB Completeness Dashboard")

    bins = get_completeness_by_bin()
    os_rates = get_os_fill_rates()
    total_rows = sum(b["row_count"] for b in bins)
    pct_total = round(100 * total_rows / DB_TARGET_ROWS, 1)

    # Overall progress bar
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Rows", f"{total_rows:,}", f"/ {DB_TARGET_ROWS:,} target")
    c2.metric("Overall Progress", f"{pct_total}%")
    c3.metric("Bins Active", f"{sum(1 for b in bins if b['row_count'] > 0)} / {len(bins)}")
    st.progress(total_rows / DB_TARGET_ROWS)
    st.caption(f"Target: {DB_TARGET_ROWS:,} rows — ~{BIN_TARGET_ROWS:,} per bin")

    st.markdown("---")

    # One line per bin — row count + fill rate + progress toward bin target
    st.markdown("**Per-Bin Status** — row count | OS fill % | progress to bin target (1,333 rows)")
    header_cols = st.columns([2, 1, 1, 3])
    header_cols[0].markdown("**Bin**")
    header_cols[1].markdown("**Rows**")
    header_cols[2].markdown("**Fill**")
    header_cols[3].markdown("**Progress to 1,333**")

    for b in bins:
        c0, c1, c2, c3 = st.columns([2, 1, 1, 3])
        c0.markdown(f"{b['status']} **{b['tag']}** {b['label']}")
        c1.markdown(f"{b['row_count']:,}")
        c2.markdown(f"{b['avg_fill_pct']}%")
        c3.progress(b["bin_progress"])

    st.markdown("---")

    # OS column fill rates (global)
    st.markdown("**OS Column Fill Rates** — across all rows in the database")
    os_cols_display = list(OS_SHORT.items())  # [(col_key, short_label), ...]
    rate_cols = st.columns(len(os_cols_display))
    for i, (col, short) in enumerate(os_cols_display):
        rate = os_rates.get(col, 0)
        color = "🟢" if rate >= 70 else ("🟡" if rate >= 40 else "🔴")
        rate_cols[i].metric(f"{color} {short}", f"{rate}%")


def _render_bin_heatmap(tag: str):
    """2D completeness matrix for a specific bin: intents × OS columns."""
    from src.rag.quality import get_completeness_2d
    from src.config import OS_SHORT

    data = get_completeness_2d(tag)
    if not data["intents"]:
        st.info(f"No rows found for bin {tag}")
        return

    st.markdown(f"**2D Completeness — {tag}** ({data['total_rows']} rows × 6 OS columns)")

    os_cols = data["os_cols"]
    short_labels = [OS_SHORT.get(c, c) for c in os_cols]

    # Build display DataFrame
    rows_data = []
    for intent in data["intents"]:
        row = {"Functional Intent": intent[:60]}
        for col, label in zip(os_cols, short_labels):
            row[label] = "✅" if data["matrix"][intent][col] else "❌"
        rows_data.append(row)

    df = pd.DataFrame(rows_data)

    # Summary row at bottom
    fill_row = {"Functional Intent": "📊 Fill Rate"}
    for col, label in zip(os_cols, short_labels):
        fill_row[label] = f"{data['col_fill'][col]}%"
    df_with_summary = pd.concat([df, pd.DataFrame([fill_row])], ignore_index=True)

    st.dataframe(df_with_summary, use_container_width=True, height=400)
    st.caption("✅ = command present | ❌ = empty (gap) | Last row = column fill rate")


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

    # Completeness dashboard (admin/superadmin only)
    from src.ui.components.auth import is_admin
    if is_admin():
        try:
            _render_completeness_dashboard(stats)
        except Exception as _e:
            st.warning(f"Completeness dashboard unavailable: {_e}")
    else:
        # Non-admin: bar chart only
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

    # 2D heatmap when a specific bin is selected (admin only)
    if tag_filter != "All" and is_admin():
        try:
            with st.expander(f"🔲 2D Completeness Heatmap — {tag_filter}", expanded=True):
                _render_bin_heatmap(tag_filter)
        except Exception as _e:
            st.warning(f"Heatmap unavailable: {_e}")

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

    # Query History (admin only)
    if is_admin():
        st.divider()
        st.subheader("📋 Query History")
        try:
            from sqlalchemy import text as _t
            from src.database.connection import get_session
            with get_session() as session:
                log_rows = session.execute(_t("""
                    SELECT created_at, username, source, query_text,
                           tag_filter, results_count, response_time_ms
                    FROM query_log
                    ORDER BY created_at DESC
                    LIMIT 200
                """)).fetchall()
            if log_rows:
                log_df = pd.DataFrame(log_rows, columns=[
                    "Time", "User", "Source", "Query",
                    "Bin", "Results", "ms"
                ])
                log_df["Time"] = pd.to_datetime(log_df["Time"]).dt.strftime("%m-%d %H:%M")
                st.dataframe(log_df, use_container_width=True, height=300)
                csv = log_df.to_csv(index=False)
                st.download_button("⬇️ Export query log", csv,
                                   "query_log.csv", "text/csv")
            else:
                st.info("No queries logged yet.")
        except Exception as _e:
            st.warning(f"Query history unavailable: {_e}")

    st.divider()

    if stats["total"] == 0:
        st.warning("Database is empty. Click below to load all seed data (~528 rows).")
        if st.button("🌱 Seed Database Now", type="primary"):
            from src.database.seed import main as seed_main
            with st.spinner("Running seed — this takes ~60s for embeddings..."):
                try:
                    seed_main(overwrite=False)
                    st.success("Seed complete! Refresh the page.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Seed failed: {e}")

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

    with st.expander("🗑️ Delete Uploaded / Non-Seed Rows"):
        st.warning(
            "Deletes all rows where source_ref is NOT 'seed' or a CSV seed file. "
            "Keeps the original ~515 seed rows. Use this to clean up bad PDF extractions."
        )
        from sqlalchemy import text as _t
        from src.database.connection import get_session
        try:
            with get_session() as session:
                sources = session.execute(_t(
                    "SELECT source_ref, COUNT(*) as cnt FROM cli_mappings "
                    "GROUP BY source_ref ORDER BY cnt DESC"
                )).fetchall()
            non_seed = [(s.source_ref, s.cnt) for s in sources
                        if s.source_ref and s.source_ref not in ("seed", "")
                        and not s.source_ref.startswith("CSV")]
            if non_seed:
                st.markdown("**Uploaded sources currently in DB:**")
                for src, cnt in non_seed:
                    c1, c2, c3 = st.columns([3, 1, 1])
                    c1.markdown(f"`{src}`")
                    c2.markdown(f"{cnt} rows")
                    if c3.button("Delete", key=f"del_{src}", type="secondary"):
                        with get_session() as session:
                            session.execute(_t(
                                "DELETE FROM cli_mappings WHERE source_ref = :src"
                            ), {"src": src})
                        st.success(f"Deleted {cnt} rows from `{src}`.")
                        st.rerun()
            else:
                st.info("No uploaded rows found — only seed data in DB.")

            st.divider()
            if st.button("🗑️ Delete ALL non-seed rows", type="secondary"):
                with get_session() as session:
                    result = session.execute(_t(
                        "DELETE FROM cli_mappings "
                        "WHERE source_ref IS NOT NULL "
                        "AND source_ref != 'seed' "
                        "AND source_ref != '' "
                        "AND source_ref NOT LIKE 'CSV%'"
                    ))
                st.success("All non-seed rows deleted. Refresh the page.")
                st.rerun()
        except Exception as _e:
            st.warning(f"Could not load source list: {_e}")
