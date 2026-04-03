"""
Config Translator UI — Sprint 14.

Streamlit tab component for the Cisco → ExtremeXOS configuration translator.
Renders:
  - Drag-and-drop / file upload / paste input
  - Source OS + Target OS dropdowns
  - Stage 1: parsed config analysis + ASCII topology (before)
  - Stage 2: translated EXOS output + intent verification + topology (after)
  - Intent calibration panel
  - Download buttons (.xos script)
"""

import io
import zipfile
import tempfile
import time
from pathlib import Path
from typing import Optional

import streamlit as st

from src.agents.config_translate_agent import (
    TARGET_OS_OPTIONS,
    SOURCE_OS_OPTIONS,
    translate_config,
)
from src.agents.intent_extract_agent import extract_all_intents
from src.agents.intent_verify_agent import (
    verify_translation,
    DEFAULT_CALIBRATION,
)
from src.parsers.cisco_config_parser import (
    parse_config,
    extract_topology,
    render_ascii_topology,
)

# ── Session state keys ────────────────────────────────────────────────────────
_SK_RAW        = "ct_raw_config"
_SK_PARSE      = "ct_parse_result"
_SK_TOPO_BEFORE= "ct_topo_before"
_SK_INTENTS    = "ct_intent_maps"
_SK_RESULT     = "ct_translation_result"
_SK_VERIFY     = "ct_verify_results"
_SK_STAGE      = "ct_stage"          # 0=input, 1=analysed, 2=translated
_SK_SRC_OS     = "ct_source_os"
_SK_TGT_OS     = "ct_target_os"
_SK_CAL        = "ct_calibration"


def _init_state():
    defaults = {
        _SK_RAW:         "",
        _SK_PARSE:       None,
        _SK_TOPO_BEFORE: "",
        _SK_INTENTS:     [],
        _SK_RESULT:      None,
        _SK_VERIFY:      [],
        _SK_STAGE:       0,
        _SK_SRC_OS:      "cisco_iosxe",
        _SK_TGT_OS:      "extreme_exos",
        _SK_CAL:         dict(DEFAULT_CALIBRATION),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _extract_text_from_upload(uploaded_file) -> str:
    """Extract plain text from uploaded file (.cfg, .txt, .conf, .docx)."""
    name = uploaded_file.name.lower()

    if name.endswith(".docx"):
        try:
            import zipfile as zf
            import xml.etree.ElementTree as ET
            with zf.ZipFile(io.BytesIO(uploaded_file.read())) as z:
                xml = z.read("word/document.xml")
            root = ET.fromstring(xml)
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            paras = root.findall(".//w:p", ns)
            lines = []
            for p in paras:
                text = "".join(r.text or "" for r in p.findall(".//w:t", ns))
                if text.strip():
                    lines.append(text)
            return "\n".join(lines)
        except Exception as e:
            st.error(f"Could not parse .docx file: {e}")
            return ""
    else:
        try:
            return uploaded_file.read().decode("utf-8", errors="replace")
        except Exception as e:
            st.error(f"Could not read file: {e}")
            return ""


def _status_badge(status: str) -> str:
    colours = {
        "verified":      "background:#163b20;color:#7ee787;border:1px solid #2ea043;",
        "unverified":    "background:#271d00;color:#d29922;border:1px solid #7d5a00;",
        "caveat":        "background:#271d00;color:#ff8800;border:1px solid #7d4000;",
        "no_equivalent": "background:#2d1515;color:#ff4444;border:1px solid #5a2020;",
        "comment":       "background:#1c1c1c;color:#555;border:1px solid #333;",
    }
    labels = {
        "verified":      "✅ Verified",
        "unverified":    "⚠ Unverified",
        "caveat":        "⚠ Caveat",
        "no_equivalent": "❌ No Equivalent",
        "comment":       "# Comment",
    }
    style = colours.get(status, colours["unverified"])
    label = labels.get(status, status)
    return f'<span style="font-size:10px;padding:1px 6px;border-radius:3px;{style}">{label}</span>'


def _confidence_colour(pct: float) -> str:
    if pct >= 90:   return "#3fb950"
    if pct >= 70:   return "#d29922"
    return "#f85149"


def _log_translation(
    source_os: str,
    target_os: str,
    sections: int,
    avg_confidence: float,
    elapsed_ms: int,
    filename: str = "",
):
    """Log a Config Translator session to query_log."""
    try:
        from src.database.models import QueryLog
        from src.database.connection import get_session
        from src.ui.components.auth import get_current_user

        label = filename or f"{source_os} → {target_os}"
        user = get_current_user()
        username = user["username"] if user else "anonymous"
        with get_session() as session:
            session.add(QueryLog(
                query_text=label,
                tag_filter=None,
                os_filter=f"{source_os} → {target_os}",
                results_count=sections,
                top_similarity=round(avg_confidence / 100, 4),
                response_time_ms=elapsed_ms,
                username=username,
                source="config_translator",
            ))
    except Exception as _e:
        pass   # never block UI for logging failures


# ── Main render ───────────────────────────────────────────────────────────────

def render_config_translator():
    _init_state()

    st.markdown("## ⚙️ Config Translator")
    st.markdown(
        "Paste or upload a complete Cisco configuration. "
        "The translator analyses it, draws the topology, then produces "
        "a fully equivalent ExtremeXOS blueprint — with intent verification "
        "and inline caveats."
    )

    # ── Template guide link ───────────────────────────────────────────────
    st.info(
        "📄 **New to this tool?** See the "
        "[Input Template Guide](https://khursheedkhanaiforgood-ai.github.io/"
        "cisco-en-cli-agent/config_translator_template.html) "
        "and download the "
        "[.cfg template](https://khursheedkhanaiforgood-ai.github.io/"
        "cisco-en-cli-agent/cisco_campus_config_template.cfg) "
        "before uploading."
    )

    # ════════════════════════════════════════════════════════════════
    # SECTION 1 — OS SELECTION
    # ════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 1. Select OS Pair")

    col_src, col_arrow, col_tgt = st.columns([5, 1, 5])

    with col_src:
        src_options = list(SOURCE_OS_OPTIONS.keys())
        src_labels  = {
            k: (v["label"] if v["active"] else f"{v['label']}  *(coming soon)*")
            for k, v in SOURCE_OS_OPTIONS.items()
        }
        src_active = [k for k, v in SOURCE_OS_OPTIONS.items() if v["active"]]
        src_idx = src_options.index(st.session_state[_SK_SRC_OS]) if st.session_state[_SK_SRC_OS] in src_options else 0
        chosen_src = st.selectbox(
            "From OS (source)",
            options=src_options,
            format_func=lambda k: src_labels[k],
            index=src_idx,
            key="ct_src_select",
        )
        if chosen_src not in src_active:
            st.warning("This source OS is not yet supported. Select Cisco IOS, IOS-XE, or NX-OS.")
        st.session_state[_SK_SRC_OS] = chosen_src

    with col_arrow:
        st.markdown("<br><br><div style='text-align:center;font-size:22px;'>→</div>", unsafe_allow_html=True)

    with col_tgt:
        tgt_options = list(TARGET_OS_OPTIONS.keys())
        tgt_labels  = {
            k: (v["label"] if v["active"] else f"{v['label']}  *(coming soon)*")
            for k, v in TARGET_OS_OPTIONS.items()
        }
        tgt_active = [k for k, v in TARGET_OS_OPTIONS.items() if v["active"]]
        tgt_idx = tgt_options.index(st.session_state[_SK_TGT_OS]) if st.session_state[_SK_TGT_OS] in tgt_options else 0
        chosen_tgt = st.selectbox(
            "To OS (target)",
            options=tgt_options,
            format_func=lambda k: tgt_labels[k],
            index=tgt_idx,
            key="ct_tgt_select",
        )
        if chosen_tgt not in tgt_active:
            st.warning("This target OS is coming in a future sprint. Select ExtremeXOS 33.x.")
        st.session_state[_SK_TGT_OS] = chosen_tgt

    translation_enabled = (
        chosen_src in src_active and chosen_tgt in tgt_active
    )

    # ════════════════════════════════════════════════════════════════
    # SECTION 2 — CONFIG INPUT
    # ════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 2. Upload or Paste Configuration")

    tab_upload, tab_paste = st.tabs(["📂 Upload File (drag & drop)", "📋 Paste Config"])

    uploaded_text = ""

    with tab_upload:
        st.markdown(
            "Drag and drop your config file below, or click **Browse files**. "
            "Accepted formats: `.cfg` `.txt` `.conf` `.docx`"
        )
        uploaded = st.file_uploader(
            "Drop config file here",
            type=["cfg", "txt", "conf", "docx"],
            label_visibility="collapsed",
            key="ct_uploader",
        )
        if uploaded:
            uploaded_text = _extract_text_from_upload(uploaded)
            if uploaded_text:
                st.success(f"✅ Loaded **{uploaded.name}** — {len(uploaded_text.splitlines())} lines")

    with tab_paste:
        pasted = st.text_area(
            "Paste your Cisco configuration here",
            height=300,
            placeholder=(
                "! --- VLAN Database ---\n"
                "vlan 10\n name DATA\n"
                "vlan 20\n name VOICE\n"
                "!\n"
                "interface GigabitEthernet1/0/1\n"
                " switchport mode access\n"
                " switchport access vlan 10\n"
                "..."
            ),
            label_visibility="collapsed",
            key="ct_paste",
        )

    raw_config = uploaded_text or pasted or ""

    # Analyse button
    col_btn1, col_btn2, _ = st.columns([2, 2, 6])
    with col_btn1:
        analyse_clicked = st.button(
            "🔍 Analyse Config",
            type="secondary",
            use_container_width=True,
            disabled=not raw_config.strip(),
        )
    with col_btn2:
        reset_clicked = st.button(
            "↺ Reset",
            use_container_width=True,
        )

    if reset_clicked:
        for k in [_SK_RAW, _SK_PARSE, _SK_TOPO_BEFORE, _SK_INTENTS,
                  _SK_RESULT, _SK_VERIFY]:
            st.session_state[k] = None if "result" in k or "parse" in k or "maps" in k else ""
        st.session_state[_SK_STAGE] = 0
        st.rerun()

    if analyse_clicked and raw_config.strip():
        with st.spinner("Parsing configuration…"):
            parse_result = parse_config(raw_config)
            topo_nodes   = extract_topology(parse_result)
            topo_ascii   = render_ascii_topology(topo_nodes, label="Input Config (Cisco)")

        st.session_state[_SK_RAW]         = raw_config
        st.session_state[_SK_PARSE]       = parse_result
        st.session_state[_SK_TOPO_BEFORE] = topo_ascii
        st.session_state[_SK_RESULT]      = None
        st.session_state[_SK_VERIFY]      = []
        st.session_state[_SK_STAGE]       = 1
        st.rerun()

    # ════════════════════════════════════════════════════════════════
    # STAGE 1 — CONFIG ANALYSIS
    # ════════════════════════════════════════════════════════════════
    if st.session_state[_SK_STAGE] >= 1 and st.session_state[_SK_PARSE]:
        pr = st.session_state[_SK_PARSE]

        st.markdown("---")
        st.markdown("### 3. Config Analysis")

        # Stats row
        s = pr.stats
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Devices",    s.get("devices", 0))
        m2.metric("Interfaces", s.get("interfaces", 0))
        m3.metric("VLANs",      s.get("vlans", 0))
        m4.metric("DHCP Pools", s.get("dhcp_pools", 0))
        m5.metric("OS Detected", pr.source_os.upper())
        m6.metric("Prose Blocks (stripped)", s.get("prose_blocks", 0))

        # Device list
        if pr.devices:
            st.markdown("**Devices found:**")
            for d in pr.devices:
                sec_types = {}
                for sec in d.sections:
                    sec_types[sec.section_type] = sec_types.get(sec.section_type, 0) + 1
                summary = "  ·  ".join(
                    f"{cnt} {t}" for t, cnt in sec_types.items()
                    if t not in ("comment", "prose")
                )
                st.markdown(f"- **{d.hostname}** — {summary}")

        # Topology before
        with st.expander("🗺 Input Topology Diagram (Cisco)", expanded=True):
            st.code(st.session_state[_SK_TOPO_BEFORE], language=None)

        # Section breakdown
        with st.expander("📋 Parsed Sections Detail"):
            for sec in pr.sections:
                if sec.section_type in ("comment", "prose"):
                    continue
                sub_count = len(sec.body)
                st.markdown(
                    f"`{sec.section_type.upper()}` &nbsp; **{sec.header}** "
                    f"<span style='color:#555;font-size:12px;'>({sub_count} sub-commands · device: {sec.device_name})</span>",
                    unsafe_allow_html=True,
                )

        if pr.prose:
            with st.expander(f"🗒 Prose / Narrative Text Stripped ({len(pr.prose)} blocks)"):
                for line in pr.prose:
                    st.markdown(
                        f"<span style='color:#555;font-size:12px;font-style:italic;'>{line}</span>",
                        unsafe_allow_html=True,
                    )

        # ── Download extracted config ─────────────────────────────
        raw_text = st.session_state[_SK_RAW]
        if raw_text:
            st.download_button(
                label="⬇ Download Extracted Config (.txt)",
                data=raw_text,
                file_name="extracted_config.txt",
                mime="text/plain",
                help="Download the plain-text CLI extracted from your uploaded file.",
            )

        # ── Translate button ──────────────────────────────────────
        st.markdown("---")
        st.markdown("### 4. Translate")

        if not translation_enabled:
            st.warning("Select a supported OS pair above to enable translation.")
        else:
            tgt_info   = TARGET_OS_OPTIONS[st.session_state[_SK_TGT_OS]]
            tgt_label  = tgt_info["label"]
            translate_btn = st.button(
                f"⚙️ Translate to {tgt_label}",
                type="primary",
                use_container_width=False,
                disabled=st.session_state[_SK_STAGE] >= 2,
            )

            if translate_btn:
                pr = st.session_state[_SK_PARSE]
                tgt_key = st.session_state[_SK_TGT_OS]
                progress_bar = st.progress(0, text="Starting translation…")
                _t_start = time.perf_counter()

                def _on_progress(step, total, msg):
                    pct = int((step / max(total, 1)) * 80)
                    progress_bar.progress(pct, text=msg)

                with st.spinner(f"Translating to {tgt_label}…"):
                    result = translate_config(
                        pr,
                        target_os_key=tgt_key,
                        progress_callback=_on_progress,
                    )

                progress_bar.progress(85, text="Extracting intents…")
                intent_maps = extract_all_intents(pr)

                progress_bar.progress(92, text="Verifying intent preservation…")
                cal = st.session_state[_SK_CAL]
                verify_results = []
                for im in intent_maps:
                    vr = verify_translation(
                        intent_map=im,
                        translated_script=result.full_script,
                        target_version=tgt_info["version"],
                        calibration=cal,
                    )
                    verify_results.append(vr)

                progress_bar.progress(100, text="Done.")

                _elapsed_ms = int((time.perf_counter() - _t_start) * 1000)
                _avg_conf = (
                    sum(v.overall_confidence for v in verify_results) / len(verify_results)
                    if verify_results else 0.0
                )
                _filename = (
                    st.session_state.get("ct_uploader") and
                    getattr(st.session_state.get("ct_uploader"), "name", "")
                ) or ""
                _log_translation(
                    source_os=result.source_os,
                    target_os=result.target_os,
                    sections=result.stats.get("sections_translated", 0),
                    avg_confidence=_avg_conf,
                    elapsed_ms=_elapsed_ms,
                    filename=_filename,
                )

                st.session_state[_SK_RESULT]  = result
                st.session_state[_SK_INTENTS] = intent_maps
                st.session_state[_SK_VERIFY]  = verify_results
                st.session_state[_SK_STAGE]   = 2
                st.rerun()

    # ════════════════════════════════════════════════════════════════
    # STAGE 2 — TRANSLATION OUTPUT
    # ════════════════════════════════════════════════════════════════
    if st.session_state[_SK_STAGE] >= 2 and st.session_state[_SK_RESULT]:
        result       = st.session_state[_SK_RESULT]
        verify_list  = st.session_state[_SK_VERIFY]
        intent_maps  = st.session_state[_SK_INTENTS]
        pr           = st.session_state[_SK_PARSE]
        tgt_info     = TARGET_OS_OPTIONS[st.session_state[_SK_TGT_OS]]

        # ── Quality Gate Banner ───────────────────────────────────
        st.markdown("---")
        st.markdown("### 5. Translation Results")

        cal = st.session_state[_SK_CAL]
        threshold = cal.get("confidence_threshold", 70)
        strictness = cal.get("strictness", "balanced")
        active_cats = cal.get("active_categories", [])

        if verify_list:
            avg_conf = sum(v.overall_confidence for v in verify_list) / len(verify_list)
            conf_col = _confidence_colour(avg_conf)
            pass_fail = avg_conf >= threshold
            pass_icon = "✅ PASS" if pass_fail else "⚠ REVIEW REQUIRED"
            pass_colour = "#238636" if pass_fail else "#9e6a03"

            st.markdown(
                f"""
<div style='background:{pass_colour}22;border:1px solid {pass_colour};border-radius:8px;
padding:14px 20px;margin-bottom:12px;display:flex;align-items:center;gap:24px;flex-wrap:wrap;'>
  <div style='font-size:36px;font-weight:800;color:{conf_col};'>{avg_conf:.0f}%</div>
  <div>
    <div style='font-size:16px;font-weight:700;color:{pass_colour};'>{pass_icon}</div>
    <div style='font-size:12px;color:#8b949e;'>Threshold: {threshold}% &nbsp;·&nbsp;
    Strictness: {strictness.title()} &nbsp;·&nbsp;
    {len(active_cats)} categories active</div>
  </div>
  <div style='margin-left:auto;font-size:12px;color:#8b949e;text-align:right;'>
    ✅ {sum(1 for v in verify_list for s in v.scores if s.status=="preserved")} preserved &nbsp;
    ⚠ {sum(1 for v in verify_list for s in v.scores if s.status in ("review","partial"))} review &nbsp;
    ❌ {sum(1 for v in verify_list for s in v.scores if s.status=="failed")} failed
  </div>
</div>""",
                unsafe_allow_html=True,
            )
        else:
            avg_conf = 0

        s = result.stats
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sections Translated", s["sections_translated"])
        c2.metric("RAG Verified Lines",  s["lines_verified"])
        c3.metric("Caveats",             s["caveats"])
        c4.metric("No Equivalents",      s["no_equivalents"])

        # ── Timing breakdown ──────────────────────────────────────
        with st.expander("⏱ Translation Timing Breakdown", expanded=False):
            t_rag   = s.get("time_rag_s", 0)
            t_claude = s.get("time_claude_s", 0)
            n_calls  = s.get("time_claude_calls", 0)
            per_call = s.get("time_claude_per_call_s", [])
            t_total  = round(t_rag + t_claude, 2)

            tc1, tc2, tc3, tc4 = st.columns(4)
            tc1.metric("Total Time",      f"{t_total}s")
            tc2.metric("RAG Lookups",     f"{t_rag}s")
            tc3.metric("Claude API",      f"{t_claude}s")
            tc4.metric("Claude Calls",    str(n_calls))

            if per_call:
                import pandas as pd
                df_t = pd.DataFrame({
                    "Section": [f"Section {i+1}" for i in range(len(per_call))],
                    "Claude API (s)": per_call,
                })
                st.bar_chart(df_t.set_index("Section"))
                st.caption("Each bar = one Claude API call (one config section). "
                           "RAG lookups run in serial before translation begins.")

        # Warnings
        if result.warnings:
            for w in result.warnings:
                st.warning(w)

        # ── PRIMARY VIEW: Cisco | EXOS side-by-side ──────────────
        st.markdown("---")
        st.markdown("### 6. Cisco → EXOS")
        st.caption(
            "Left: original Cisco config · Right: translated ExtremeXOS commands. "
            "Expand **Annotated Detail** below for caveats, verification badges, and section-by-section diff."
        )

        cisco_col, exos_col = st.columns(2)
        with cisco_col:
            st.markdown(
                "<div style='font-size:12px;font-weight:600;color:#8b949e;"
                "margin-bottom:4px;'>🔵 Original (Cisco)</div>",
                unsafe_allow_html=True,
            )
            st.code(st.session_state[_SK_RAW], language="text")

        with exos_col:
            st.markdown(
                f"<div style='font-size:12px;font-weight:600;color:#3fb950;"
                f"margin-bottom:4px;'>🟢 Translated ({tgt_info['version']})</div>",
                unsafe_allow_html=True,
            )
            st.code(result.clean_script, language="text")

        # ── Annotated detail (collapsed) ─────────────────────────
        with st.expander("📋 Annotated Detail — caveats, no-equivalents & section diff", expanded=False):
            st.caption("Each section: original Cisco (left) · annotated EXOS with badges (right).")

            for ts in result.sections:
                sec_label = f"`{ts.original.section_type.upper()}` — {ts.original.header}"
                rag_badge = f"🔍 {ts.rag_hits} RAG" if ts.rag_hits else ""
                caveat_badge = "⚠ caveat" if ts.has_caveats else ""
                noeq_badge = "❌ no equiv" if ts.has_no_equivalent else ""
                badges = "  ·  ".join(b for b in [rag_badge, caveat_badge, noeq_badge] if b)

                st.markdown(
                    f"**{sec_label}**"
                    + (f"  <span style='font-size:11px;color:#8b949e;'>{badges}</span>" if badges else ""),
                    unsafe_allow_html=True,
                )
                orig_col2, trans_col2 = st.columns(2)
                with orig_col2:
                    st.code(ts.original.raw_text, language="text")
                with trans_col2:
                    lines_html = []
                    for tl in ts.translated_lines:
                        if not tl.text.strip():
                            lines_html.append("<div style='height:6px'></div>")
                            continue
                        badge_html = _status_badge(tl.status)
                        colour = {
                            "verified":      "#7ee787",
                            "unverified":    "#d29922",
                            "caveat":        "#ff8800",
                            "no_equivalent": "#f85149",
                            "comment":       "#8b949e",
                        }.get(tl.status, "#c9d1d9")
                        lines_html.append(
                            f"<div style='font-family:SF Mono,Consolas,monospace;font-size:12px;"
                            f"color:{colour};margin:1px 0;padding:2px 4px;'>"
                            f"{tl.text}&nbsp;&nbsp;{badge_html}</div>"
                        )
                    st.markdown(
                        f"<div style='background:#0d1117;border:1px solid #30363d;"
                        f"border-radius:6px;padding:10px;margin-bottom:12px;'>{''.join(lines_html)}</div>",
                        unsafe_allow_html=True,
                    )

        # ── Topology before & after (collapsed) ───────────────────
        with st.expander("🗺 Topology — Before & After", expanded=False):
            topo_col1, topo_col2 = st.columns(2)
            with topo_col1:
                st.markdown("**🔵 Before (Cisco)**")
                st.code(st.session_state[_SK_TOPO_BEFORE], language=None)
            with topo_col2:
                st.markdown(f"**🟢 After ({tgt_info['version']})**")
                after_topo_nodes = extract_topology(parse_config(result.full_script))
                after_topo = render_ascii_topology(
                    after_topo_nodes,
                    label=f"Translated Config ({tgt_info['version']})"
                ) if after_topo_nodes else "(topology not parseable from EXOS output)"
                st.code(after_topo, language=None)

        # ── Intent Verification ───────────────────────────────────
        if verify_list:
            st.markdown("---")
            st.markdown("### 8. Intent Verification")

            for vr, im in zip(verify_list, intent_maps):
                conf_col = _confidence_colour(vr.overall_confidence)
                pass_icon = "✅" if vr.pass_threshold else "⚠"
                st.markdown(
                    f"**Device: {vr.device_name}** &nbsp; "
                    f"<span style='font-size:20px;font-weight:700;color:{conf_col};'>"
                    f"{vr.overall_confidence:.0f}%</span> &nbsp; "
                    f"{pass_icon} {'PASS' if vr.pass_threshold else 'REVIEW REQUIRED'} "
                    f"(threshold: {vr.calibration['confidence_threshold']}%)",
                    unsafe_allow_html=True,
                )

                # Intent table
                table_rows = []
                for score in vr.scores:
                    icon = {
                        "preserved": "✅", "review": "⚠",
                        "partial": "⚠", "failed": "❌",
                    }.get(score.status, "?")
                    conf_c = _confidence_colour(score.confidence)
                    table_rows.append(
                        f"| {score.intent.id} | {score.intent.category} | "
                        f"<span style='color:{conf_c};font-weight:600'>{score.confidence:.0f}%</span> | "
                        f"{icon} {score.status.title()} | {score.note} |"
                    )
                if table_rows:
                    st.markdown(
                        "| ID | Category | Confidence | Status | Note |\n"
                        "|----|----|----|----|----|\n" +
                        "\n".join(table_rows),
                        unsafe_allow_html=True,
                    )

            # ── Re-verify with updated sidebar settings ───────────
            st.caption(
                "To adjust quality settings (threshold, strictness, categories), "
                "use the **🎯 Translation Quality** panel in the sidebar, then click Re-verify below."
            )
            if st.button("🔄 Re-verify with current quality settings", type="secondary"):
                new_verify = []
                for im in intent_maps:
                    tgt_info2 = TARGET_OS_OPTIONS[st.session_state[_SK_TGT_OS]]
                    vr2 = verify_translation(
                        intent_map=im,
                        translated_script=result.full_script,
                        target_version=tgt_info2["version"],
                        calibration=st.session_state[_SK_CAL],
                    )
                    new_verify.append(vr2)
                st.session_state[_SK_VERIFY] = new_verify
                st.rerun()

        # ── Download buttons ──────────────────────────────────────
        st.markdown("---")
        st.markdown("### 9. Download")

        dl1, dl2, dl3, dl4 = st.columns(4)

        with dl1:
            st.download_button(
                label="⬇ Download .xos (clean)",
                data=result.clean_script,
                file_name=f"translated_{st.session_state[_SK_TGT_OS]}.xos",
                mime="text/plain",
                use_container_width=True,
                help="Commands only — no annotation comments.",
            )

        with dl2:
            st.download_button(
                label="⬇ Download .txt (clean)",
                data=result.clean_script,
                file_name=f"translated_{st.session_state[_SK_TGT_OS]}.txt",
                mime="text/plain",
                use_container_width=True,
                help="Commands only — no annotation comments.",
            )

        with dl3:
            # Intent verification report as text
            if verify_list:
                report_lines = [
                    f"Config Translator — Intent Verification Report",
                    f"Target: {tgt_info['version']}",
                    "=" * 60,
                    "",
                ]
                for vr in verify_list:
                    report_lines.append(vr.summary_text())
                    report_lines.append("")
                report_text = "\n".join(report_lines)
                st.download_button(
                    label="⬇ Download Verification Report",
                    data=report_text,
                    file_name="intent_verification_report.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

        with dl4:
            # ZIP: clean script + annotated script + report + original
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w") as zf:
                zf.writestr(f"translated_{st.session_state[_SK_TGT_OS]}_clean.xos", result.clean_script)
                zf.writestr(f"translated_{st.session_state[_SK_TGT_OS]}_annotated.xos", result.full_script)
                zf.writestr("original_config.txt", st.session_state[_SK_RAW])
                if verify_list:
                    zf.writestr("intent_verification_report.txt", report_text)
                zf.writestr("topology_before.txt", st.session_state[_SK_TOPO_BEFORE])
            zip_buf.seek(0)
            st.download_button(
                label="⬇ Download Full Package (.zip)",
                data=zip_buf,
                file_name="config_translation_package.zip",
                mime="application/zip",
                use_container_width=True,
            )

        # Re-translate button
        if st.button("↺ Translate Again (new config)", use_container_width=False):
            for k in [_SK_RESULT, _SK_VERIFY, _SK_INTENTS, _SK_PARSE,
                      _SK_TOPO_BEFORE, _SK_RAW]:
                st.session_state[k] = None
            st.session_state[_SK_STAGE] = 0
            st.rerun()
