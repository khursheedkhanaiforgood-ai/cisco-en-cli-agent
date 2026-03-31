"""
Data Ingest Panel — lets users upload documents/CSVs, and manages
web crawler results with approval before DB insertion.
"""
import streamlit as st
import io
import time


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


def _extract_and_preview(uploaded_file, os_col: str, max_pages: int):
    import tempfile, os
    from pathlib import Path

    with st.spinner(f"Extracting CLI commands from {uploaded_file.name}..."):
        # Save to temp file
        suffix = Path(uploaded_file.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = Path(tmp.name)

        try:
            if suffix.lower() == ".pdf":
                from src.extractors.pdf_extractor import extract_from_voss_pdf, extract_from_exos_pdf
                # Auto-select extractor based on OS
                if "voss" in os_col:
                    records = extract_from_voss_pdf(tmp_path, tmp_path.with_suffix(".json"), max_pages or 0)
                else:
                    records = extract_from_exos_pdf(tmp_path, tmp_path.with_suffix(".json"), max_pages or 0)
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

    st.success(f"Found **{len(records)} records** — review before inserting:")
    _show_approval_table(records, os_col, source_name=uploaded_file.name)


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
            # Treat as section header
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


def _show_approval_table(records: list[dict], os_col: str, source_name: str):
    """Show extracted records for user approval before DB insertion."""
    import pandas as pd

    df = pd.DataFrame(records)
    display_cols = [c for c in ["tag", "functional_intent", os_col, "source_ref"] if c in df.columns]

    st.dataframe(df[display_cols], use_container_width=True, height=400)

    col1, col2 = st.columns(2)
    if col1.button(f"✅ Insert all {len(records)} records", type="primary"):
        _insert_approved_records(records, os_col)
    if col2.button("❌ Discard — do not insert"):
        st.info("Records discarded. Nothing was added to the database.")


def _insert_approved_records(records: list[dict], os_col: str):
    from src.extractors.pdf_extractor import load_extracted_to_db
    import json, tempfile, os
    from pathlib import Path

    with st.spinner("Inserting approved records..."):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(records, tmp)
            tmp_path = Path(tmp.name)
        try:
            result = load_extracted_to_db(tmp_path, os_col)
        finally:
            os.unlink(tmp_path)

    st.success(f"Inserted **{result['added']} records** into the database.")
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


def _preview_csv(uploaded_file, overwrite: bool):
    import pandas as pd, csv, io

    content = uploaded_file.read().decode("utf-8")
    df = pd.read_csv(io.StringIO(content))
    st.markdown(f"**{len(df)} rows detected** — preview:")
    st.dataframe(df.head(20), use_container_width=True)

    missing = [c for c in ["tag", "functional_intent"] if c not in df.columns]
    if missing:
        st.error(f"Missing required columns: {missing}")
        return

    if st.button(f"✅ Insert {len(df)} rows", type="primary"):
        _insert_csv(content, overwrite)


def _insert_csv(csv_content: str, overwrite: bool):
    import tempfile, os
    from pathlib import Path

    with st.spinner("Inserting CSV rows..."):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False,
                                         encoding="utf-8") as tmp:
            tmp.write(csv_content)
            tmp_path = Path(tmp.name)
        try:
            from src.extractors.csv_loader import load_csv
            result = load_csv(tmp_path, expected_tag="[MGMT-OPS]", overwrite=overwrite)
        finally:
            os.unlink(tmp_path)

    st.success(f"Added: **{result['added']}** | Skipped: {result['skipped']} | Errors: {result['errors']}")


# ─────────────────────────────────────────────────────────────────────────────
# WEB CRAWLER WITH APPROVAL
# ─────────────────────────────────────────────────────────────────────────────

def _render_crawler():
    st.subheader("Web Crawler — Find New CLI Commands")
    st.markdown(
        "The crawler searches vendor documentation sites for new CLI commands. "
        "**Results are shown for your approval before anything is inserted into the database.**"
    )

    from src.config import VENDOR_SEED_URLS, OS_COLUMNS

    col1, col2 = st.columns(2)
    with col1:
        url_source = st.selectbox(
            "Source",
            ["Custom URL"] + list(VENDOR_SEED_URLS.keys()),
        )
    with col2:
        os_col = st.selectbox("Target OS column", OS_COLUMNS)

    if url_source == "Custom URL":
        crawl_url = st.text_input("Enter URL to crawl",
                                  placeholder="https://documentation.extremenetworks.com/...")
    else:
        crawl_url = VENDOR_SEED_URLS[url_source]
        st.info(f"URL: `{crawl_url}`")
        os_col = url_source  # Match OS to source

    col1, col2 = st.columns(2)
    with col1:
        max_pages = st.slider("Max pages", 5, 100, 20,
                              help="Crawler stops after this many pages. Keep low to avoid long waits.")
    with col2:
        timeout_sec = st.slider("Timeout (seconds)", 10, 120, 30,
                                help="Crawler stops if this time limit is exceeded.")

    if st.button("🕷️ Start Crawler (dry run — preview only)", type="primary"):
        if not crawl_url:
            st.warning("Please enter a URL.")
        else:
            _run_crawler_preview(crawl_url, os_col, max_pages, timeout_sec)


def _run_crawler_preview(url: str, os_col: str, max_pages: int, timeout_sec: int):
    from src.extractors.web_crawler import crawl_url
    import threading

    results_holder = {}
    done = threading.Event()

    def _crawl():
        try:
            result = crawl_url(url, os_col=os_col, max_pages=max_pages,
                               rate_limit=0.5, dry_run=True)
            results_holder["result"] = result
        except Exception as e:
            results_holder["error"] = str(e)
        finally:
            done.set()

    with st.spinner(f"Crawling up to {max_pages} pages (timeout: {timeout_sec}s)..."):
        t = threading.Thread(target=_crawl, daemon=True)
        t.start()
        done.wait(timeout=timeout_sec)

    if "error" in results_holder:
        st.error(f"Crawler error: {results_holder['error']}")
        return

    if not done.is_set():
        st.warning(f"Crawler timed out after {timeout_sec}s. Showing partial results.")

    result = results_holder.get("result", {})
    records = result.get("records", 0)
    crawled = result.get("crawled", 0)

    st.info(f"Crawled **{crawled} pages**, found **{records} potential records**.")

    if records == 0:
        st.info("No new CLI commands found. Try a more specific URL or different OS column.")
        return

    # For approval, we need the actual record list — re-run briefly to get data
    st.success(f"**{records} records ready for review.** Run the crawler again with 'Insert' to approve and save.")

    col1, col2 = st.columns(2)
    if col1.button(f"✅ Approve & Insert {records} records", type="primary"):
        with st.spinner("Inserting approved crawler results..."):
            final = crawl_url(url, os_col=os_col, max_pages=max_pages,
                              rate_limit=0.5, dry_run=False)
        st.success(f"Inserted **{final.get('inserted', 0)} records** into the database.")
    if col2.button("❌ Discard — do not insert"):
        st.info("Crawler results discarded.")
