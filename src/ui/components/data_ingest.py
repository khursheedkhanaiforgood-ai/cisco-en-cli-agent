"""
Data Ingest Panel — lets users upload documents/CSVs, and manages
web crawler results with approval before DB insertion.
"""
import streamlit as st
import io
import time
import re


# ─────────────────────────────────────────────────────────────────────────────
# USER DOCUMENT UPLOAD
# ─────────────────────────────────────────────────────────────────────────────

def render_data_ingest():
    st.header("📥 Add Data to the Database")
    st.markdown(
        "Upload vendor documentation, CSV files, or trigger the web crawler. "
        "All new data is previewed **before** it is inserted — you approve it first."
    )

    tab_upload, tab_csv, tab_crawler = st.tabs([
        "📄 Upload Document (PDF/TXT)",
        "📊 Upload CSV",
        "🌐 Web Crawler",
    ])

    with tab_upload:
        _render_document_upload()

    with tab_csv:
        _render_csv_upload()

    with tab_crawler:
        _render_crawler()


def _render_document_upload():
    st.subheader("Upload a PDF or Text Document")
    st.markdown(
        "Supported: vendor CLI user guides, command references, config guides. "
        "The system extracts CLI commands using font/pattern detection."
    )

    from src.config import FUNCTIONAL_TAGS, TAG_LABELS, OS_COLUMNS

    col1, col2 = st.columns(2)
    with col1:
        os_col = st.selectbox(
            "Target OS column",
            OS_COLUMNS,
            help="Which OS does this document cover?",
        )
    with col2:
        default_tag = st.selectbox(
            "Default functional bin",
            ["Auto-detect"] + FUNCTIONAL_TAGS,
            help="Auto-detect classifies each section independently",
        )

    uploaded = st.file_uploader(
        "Drop your PDF or TXT file here",
        type=["pdf", "txt"],
        accept_multiple_files=False,
    )

    max_pages = st.slider("Max pages to extract (0 = all)", 0, 500, 0,
                          help="Limit for testing. Use 0 for full document.")

    if uploaded and st.button("🔍 Extract & Preview", type="primary"):
        _extract_and_preview(uploaded, os_col, max_pages)

    # Render cached approval table if extraction already ran
    elif st.session_state.get("_pdf_records") and st.session_state.get("_pdf_os_col"):
        _render_pdf_approval(ctx="upload")


def _extract_and_preview(uploaded_file, os_col: str, max_pages: int):
    import tempfile, os
    from pathlib import Path

    with st.spinner(f"Extracting CLI commands from {uploaded_file.name}..."):
        suffix = Path(uploaded_file.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = Path(tmp.name)

        try:
            if suffix.lower() == ".pdf":
                from src.extractors.pdf_extractor import (
                    detect_pdf_format, extract_from_pdf,
                    extract_from_cisco_cr_pdf, extract_from_extreme_cr_pdf,
                )
                fmt = detect_pdf_format(tmp_path)
                _EXTRACTOR_LABEL = {
                    "cisco_cr_pdf":   "Cisco Command Reference",
                    "extreme_cr_pdf": "Extreme Networks CR",
                    "pdf":            "Generic (EXOS/VOSS User Guide)",
                }
                st.info(f"Auto-detected format: **{_EXTRACTOR_LABEL.get(fmt, fmt)}**")
                if fmt == "cisco_cr_pdf":
                    records = extract_from_cisco_cr_pdf(
                        tmp_path, os_col=os_col,
                        source_name=uploaded_file.name, max_pages=max_pages or 0,
                    )
                elif fmt == "extreme_cr_pdf":
                    records = extract_from_extreme_cr_pdf(
                        tmp_path, os_col=os_col,
                        source_name=uploaded_file.name, max_pages=max_pages or 0,
                    )
                else:
                    records = extract_from_pdf(
                        tmp_path, os_col=os_col,
                        source_name=uploaded_file.name, max_pages=max_pages or 0,
                    )
            elif suffix.lower() == ".txt":
                records = _extract_from_txt(tmp_path, os_col)
            else:
                st.error(f"Unsupported file type: {suffix}")
                return
        finally:
            os.unlink(tmp_path)

    if not records:
        st.warning("No CLI commands found in this document. Try a different file or check the OS column selection.")
        return

    # Cache in session_state so approval table survives reruns
    st.session_state["_pdf_records"] = records
    st.session_state["_pdf_os_col"] = os_col
    st.session_state["_pdf_source"] = uploaded_file.name
    st.session_state["_pdf_inserted"] = False
    _render_pdf_approval()


def _render_pdf_approval(ctx: str = "upload"):
    """Render cached PDF approval table — persists across reruns.
    ctx: unique prefix for button keys to avoid duplicate key errors across tabs.
    """
    records = st.session_state.get("_pdf_records", [])
    os_col = st.session_state.get("_pdf_os_col", "")
    source_name = st.session_state.get("_pdf_source", "upload")

    if not records:
        return

    import pandas as pd
    from sqlalchemy import text as _t
    from src.database.connection import get_session

    # Classify each record as MERGE (intent exists) or NEW
    try:
        with get_session() as session:
            existing_intents = set(
                session.execute(
                    _t("SELECT LOWER(TRIM(functional_intent)) FROM cli_mappings")
                ).scalars().all()
            )
        def _action(r):
            return "↗ merge" if r["functional_intent"].lower().strip() in existing_intents else "✨ new"
        for r in records:
            r["_action"] = _action(r)
    except Exception:
        for r in records:
            r["_action"] = "?"

    df = pd.DataFrame(records)
    n_merge = sum(1 for r in records if r["_action"] == "↗ merge")
    n_new   = len(records) - n_merge

    st.success(
        f"**{len(records)} records** extracted from `{source_name}` — "
        f"✨ **{n_new} new rows** to insert | ↗ **{n_merge} existing rows** to fill `{os_col}`"
    )
    st.caption(
        "↗ merge = intent already in DB — will fill the OS column on that row  |  "
        "✨ new = not yet in DB — will insert a new row"
    )

    # ── Action buttons at TOP so they're always visible ───────────────────────
    col1, col2 = st.columns(2)
    apply = col1.button(
        f"✅ Apply — insert {n_new} new + merge {n_merge} existing",
        type="primary", key=f"_{ctx}_pdf_insert", use_container_width=True,
    )
    discard = col2.button(
        "❌ Discard — do not insert",
        key=f"_{ctx}_pdf_discard", use_container_width=True,
    )

    if apply:
        _insert_approved_records(records, os_col)
        st.session_state.pop("_pdf_records", None)
        st.session_state.pop("_pdf_os_col", None)
        st.session_state.pop("_pdf_source", None)
        return
    if discard:
        st.session_state.pop("_pdf_records", None)
        st.session_state.pop("_pdf_os_col", None)
        st.session_state.pop("_pdf_source", None)
        st.info("Records discarded. Nothing was added to the database.")
        st.rerun()

    # ── Preview table below the buttons ───────────────────────────────────────
    display_cols = [c for c in ["_action", "tag", "functional_intent", os_col, "source_ref"]
                    if c in df.columns]

    col_config = {
        "_action":           st.column_config.TextColumn("Action",   width="small"),
        "tag":               st.column_config.TextColumn("Bin",      width="small"),
        "functional_intent": st.column_config.TextColumn("Intent",   width="large"),
        os_col:              st.column_config.TextColumn("Commands",  width="large"),
        "source_ref":        st.column_config.TextColumn("Source",   width="medium"),
    }

    page_size = 100
    total_pages = max(1, (len(df) + page_size - 1) // page_size)
    if total_pages > 1:
        page = st.number_input(
            f"Page (1–{total_pages})", min_value=1, max_value=total_pages, value=1, step=1,
            key=f"_{ctx}_pdf_page"
        )
        start = (page - 1) * page_size
        st.caption(f"Rows {start + 1}–{min(start + page_size, len(df))} of {len(df)}")
        st.dataframe(df[display_cols].iloc[start:start + page_size],
                     use_container_width=True, height=420, column_config=col_config)
    else:
        st.dataframe(df[display_cols], use_container_width=True, height=420,
                     column_config=col_config)


def _extract_from_txt(path, os_col: str) -> list[dict]:
    """Basic extraction from plain text (CLI command lines)."""
    import re
    from src.extractors.pdf_extractor import CLI_VERB_PATTERNS, classify_tag

    records = []
    with open(path) as f:
        lines = f.readlines()

    current_section = "Extracted commands"
    commands = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if len(line) < 60 and not line.startswith(" ") and not CLI_VERB_PATTERNS.match(line):
            if commands:
                records.append({
                    "tag": classify_tag(current_section),
                    "functional_intent": current_section[:200],
                    "commands_text": " | ".join(commands[:10]),
                    os_col: " | ".join(commands[:10]),
                    "source_ref": "user-upload",
                    "page_ref": "",
                })
                commands = []
            current_section = line
        elif CLI_VERB_PATTERNS.match(line):
            commands.append(line)

    if commands:
        records.append({
            "tag": classify_tag(current_section),
            "functional_intent": current_section[:200],
            "commands_text": " | ".join(commands[:10]),
            os_col: " | ".join(commands[:10]),
            "source_ref": "user-upload",
        })
    return records


def _insert_approved_records(records: list[dict], os_col: str):
    from src.extractors.pdf_extractor import load_extracted_to_db
    import json, tempfile, os
    from pathlib import Path

    with st.spinner("Inserting approved records — generating embeddings..."):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(records, tmp)
            tmp_path = Path(tmp.name)
        try:
            result = load_extracted_to_db(tmp_path, os_col)
        finally:
            os.unlink(tmp_path)

    st.success(
        f"✅ **{result['added']} new rows inserted** | "
        f"↗ **{result.get('merged', 0)} existing rows updated** with `{os_col}` commands"
    )
    if result.get("errors", 0):
        st.warning(f"{result['errors']} errors — check logs.")
    st.info("Refresh the page to see updated row counts in the sidebar.")


# ─────────────────────────────────────────────────────────────────────────────
# CSV UPLOAD
# ─────────────────────────────────────────────────────────────────────────────

def _render_csv_upload():
    st.subheader("Upload a CLI Mapping CSV")
    st.markdown(
        "CSV must follow the standard format. "
        "[Download template ↓](#)"
    )

    # Template download
    template = (
        "tag,functional_intent,cisco_ios,cisco_iosxe,cisco_nxos,"
        "extreme_exos,extreme_voss,extreme_slxos,"
        "negation_cisco,negation_en,notes,source_ref,page_ref,confidence,is_verified\n"
        "[L2-SEG],Example — Create VLAN 10,vlan 10,vlan 10,vlan 10,"
        "create vlan v10 tag 10,vlan create 10 name v10 type port,,,"
        "no vlan 10,delete vlan v10,Example row,user-upload,,1.0,false\n"
    )
    st.download_button("⬇️ Download CSV template", data=template,
                       file_name="cli_mapping_template.csv", mime="text/csv")

    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    overwrite = st.checkbox("Overwrite existing rows with same intent", value=False)

    if uploaded and st.button("🔍 Preview CSV", type="primary"):
        _preview_csv(uploaded, overwrite)

    # Render cached CSV approval if preview already ran
    elif st.session_state.get("_csv_content"):
        _render_csv_approval()


def _preview_csv(uploaded_file, overwrite: bool):
    import pandas as pd

    content = uploaded_file.read().decode("utf-8")
    df = pd.read_csv(io.StringIO(content))

    missing = [c for c in ["tag", "functional_intent"] if c not in df.columns]
    if missing:
        st.error(f"Missing required columns: {missing}")
        return

    # Cache in session_state
    st.session_state["_csv_content"] = content
    st.session_state["_csv_overwrite"] = overwrite
    st.session_state["_csv_row_count"] = len(df)
    _render_csv_approval()


def _render_csv_approval():
    """Render cached CSV approval table — persists across reruns."""
    import pandas as pd

    content = st.session_state.get("_csv_content", "")
    overwrite = st.session_state.get("_csv_overwrite", False)
    row_count = st.session_state.get("_csv_row_count", 0)

    if not content:
        return

    df = pd.read_csv(io.StringIO(content))
    st.markdown(f"**{len(df)} rows detected** — preview (first 20 rows):")
    st.dataframe(df.head(20), use_container_width=True)

    if len(df) > 20:
        with st.expander(f"Show all {len(df)} rows"):
            page_size = 100
            total_pages = max(1, (len(df) + page_size - 1) // page_size)
            page = st.number_input(
                f"Page (1–{total_pages})", min_value=1, max_value=total_pages, value=1, step=1,
                key="_csv_page"
            )
            start = (page - 1) * page_size
            st.dataframe(df.iloc[start:start + page_size], use_container_width=True, height=500)

    col1, col2 = st.columns(2)
    if col1.button(f"✅ Insert {len(df)} rows", type="primary", key="_csv_insert"):
        _insert_csv(content, overwrite)
        st.session_state.pop("_csv_content", None)
        st.session_state.pop("_csv_overwrite", None)
        st.session_state.pop("_csv_row_count", None)
    if col2.button("❌ Discard", key="_csv_discard"):
        st.session_state.pop("_csv_content", None)
        st.session_state.pop("_csv_overwrite", None)
        st.session_state.pop("_csv_row_count", None)
        st.info("CSV discarded.")
        st.rerun()


def _insert_csv(csv_content: str, overwrite: bool):
    import tempfile, os
    from pathlib import Path

    with st.spinner("Inserting CSV rows — generating embeddings..."):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False,
                                         encoding="utf-8") as tmp:
            tmp.write(csv_content)
            tmp_path = Path(tmp.name)
        try:
            from src.extractors.csv_loader import load_csv
            # Use empty string as fallback tag — actual tag comes from the CSV's tag column
            result = load_csv(tmp_path, expected_tag="", overwrite=overwrite)
        finally:
            os.unlink(tmp_path)

    st.success(f"Added: **{result['added']}** | Skipped: {result['skipped']} | Errors: {result['errors']}")
    st.info("Refresh the page to see updated row counts in the sidebar.")


# ─────────────────────────────────────────────────────────────────────────────
# WEB CRAWLER — 3-phase: Discover → Select → Extract
# ─────────────────────────────────────────────────────────────────────────────

def _render_crawler():
    st.subheader("Web Crawler — Discover & Import Documents")
    st.markdown(
        "Paste any vendor documentation index page. The crawler finds all documents "
        "on that page, lets you **choose which ones** to extract, then imports the "
        "commands into the database using the same merge/insert logic as PDF upload."
    )

    from src.config import OS_COLUMNS

    # ── Phase 1: URL input + Discover ────────────────────────────────────────
    col1, col2 = st.columns([4, 1])
    with col1:
        url = st.text_input(
            "Documentation index URL",
            placeholder="https://www.cisco.com/c/en/us/.../products-command-reference-list.html",
            value=st.session_state.get("_crawler_url", ""),
            label_visibility="collapsed",
        )
    with col2:
        os_col = st.selectbox("OS column", OS_COLUMNS, key="_crawler_os_col")

    discover_btn = st.button("🔍 Discover Documents", type="primary")

    if discover_btn and url:
        st.session_state["_crawler_url"] = url
        st.session_state.pop("_crawler_docs", None)
        st.session_state.pop("_crawler_selected", None)
        with st.spinner("Fetching page and discovering document links..."):
            from src.extractors.web_crawler import discover_documents
            docs = discover_documents(url)
        if docs and "error" in docs[0]:
            st.error(docs[0]["error"])
        elif not docs:
            st.warning("No document links found on that page. Try a more specific URL.")
        else:
            st.session_state["_crawler_docs"] = docs
            st.rerun()

    # ── Show approval table if extraction already ran ────────────────────────
    if st.session_state.get("_pdf_records") and st.session_state.get("_pdf_os_col"):
        _render_pdf_approval(ctx="crawler")
        return

    # ── Phase 2: Document selection ──────────────────────────────────────────
    docs = st.session_state.get("_crawler_docs")
    if not docs:
        st.info("Enter a documentation index URL above and click **Discover Documents**.")
        return

    pdfs  = [d for d in docs if d["doc_type"] == "pdf"]
    htmls = [d for d in docs if d["doc_type"] == "html"]
    st.success(f"Found **{len(docs)} documents** — {len(pdfs)} PDFs, {len(htmls)} HTML pages")

    import pandas as pd
    doc_df = pd.DataFrame([
        {"#": i + 1, "Type": d["doc_type"].upper(), "Title": d["title"], "URL": d["url"]}
        for i, d in enumerate(docs)
    ])
    st.dataframe(doc_df, use_container_width=True, height=300)

    st.markdown("**Select documents to extract from:**")
    titles = [f"{d['doc_type'].upper()} — {d['title'][:80]}" for d in docs]

    # Persist selection explicitly in session_state so it survives reruns
    if "_crawler_selected" not in st.session_state:
        st.session_state["_crawler_selected"] = []

    selected_titles = st.multiselect(
        "Documents",
        options=titles,
        default=st.session_state["_crawler_selected"],
        label_visibility="collapsed",
        key="_crawler_multiselect",
    )
    # Keep session_state in sync with widget
    st.session_state["_crawler_selected"] = selected_titles

    max_pdf_pages = st.slider(
        "Max pages per PDF (0 = all)", 0, 500, 50,
        help="Use a low limit to test before doing a full extract.",
        key="_crawler_max_pages",
    )

    if selected_titles:
        selected_docs = [docs[titles.index(t)] for t in selected_titles]
        st.info(f"**{len(selected_docs)} document(s) selected** — OS: `{os_col}`")
        extract_btn = st.button(
            f"⬇️ Extract from {len(selected_docs)} document(s)",
            type="primary", key="_crawler_extract",
            use_container_width=True,
        )
    else:
        st.info("Select one or more documents above, then click Extract.")
        extract_btn = False

    # ── Phase 3: Extract selected documents ──────────────────────────────────
    if extract_btn:
        all_records = []
        errors = []

        progress = st.progress(0)
        status = st.empty()

        from src.extractors.web_crawler import extract_from_doc

        for i, doc in enumerate(selected_docs):
            status.info(f"Extracting {i + 1}/{len(selected_docs)}: {doc['title'][:60]}...")
            result = extract_from_doc(
                doc["url"],
                os_col=os_col,
                max_pages=max_pdf_pages,
            )
            if result.get("error"):
                errors.append(f"{doc['title'][:50]}: {result['error']}")
            else:
                all_records.extend(result["records"])
            progress.progress((i + 1) / len(selected_docs))
            time.sleep(0.3)

        progress.empty()
        status.empty()

        if errors:
            for err in errors:
                st.warning(f"⚠️ {err}")

        if not all_records:
            st.error("No CLI commands extracted. Documents may be login-gated, JS-rendered, or have no command blocks.")
            return

        # Store for approval and clear crawler state
        st.session_state["_pdf_records"] = all_records
        st.session_state["_pdf_os_col"]  = os_col
        st.session_state["_pdf_source"]  = f"{len(selected_docs)} crawled doc(s)"
        st.session_state.pop("_crawler_docs", None)
        st.session_state.pop("_crawler_selected", None)
        st.rerun()
