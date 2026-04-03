"""
Translation Quality Panel — sidebar component.
Mirrors RAG Tuning panel UX for the Config Translator quality gate.
Stores calibration in st.session_state["ct_calibration"].
"""
import streamlit as st

from src.agents.intent_verify_agent import DEFAULT_CALIBRATION

_SK_CAL = "ct_calibration"


def init_translation_quality():
    """Call once at app startup to initialise calibration session state."""
    if _SK_CAL not in st.session_state:
        st.session_state[_SK_CAL] = dict(DEFAULT_CALIBRATION)


def get_translation_quality_settings() -> dict:
    """Return current calibration settings from session state."""
    return st.session_state.get(_SK_CAL, dict(DEFAULT_CALIBRATION))


def render_translation_quality_panel():
    """Render the Translation Quality tuning panel. Call inside st.sidebar."""
    st.markdown("### 🎯 Translation Quality")

    with st.expander("Calibration settings", expanded=False):
        cal = st.session_state.get(_SK_CAL, dict(DEFAULT_CALIBRATION))

        # ── Confidence Threshold ────────────────────────────────────────────
        st.markdown("**Confidence Threshold**")
        st.caption(
            "Minimum weighted intent score for a translation to PASS. "
            "Below this = flagged for review. Analogous to RAG similarity threshold."
        )
        threshold = st.slider(
            "Threshold %", min_value=50, max_value=95,
            value=cal.get("confidence_threshold", 70), step=5,
            key="ct_threshold_slider",
            help="70% recommended · 85%+ for critical deployments · 55% for exploratory review",
        )
        _threshold_advice(threshold)

        st.divider()

        # ── Strictness ──────────────────────────────────────────────────────
        st.markdown("**Translation Strictness**")
        st.caption("How strictly to score intents during verification.")
        strictness = st.radio(
            "Strictness",
            options=["strict", "balanced", "lenient"],
            index=["strict", "balanced", "lenient"].index(
                cal.get("strictness", "balanced")
            ),
            key="ct_strictness_radio",
            horizontal=True,
            help=(
                "Strict: exact EXOS syntax must match. "
                "Balanced: functional equivalence counts. "
                "Lenient: topology/reachability preservation only."
            ),
        )
        _strictness_advice(strictness)

        st.divider()

        # ── Active Categories ───────────────────────────────────────────────
        st.markdown("**Active Intent Categories**")
        st.caption("Only active categories count toward the confidence score.")

        all_cats = list(DEFAULT_CALIBRATION["category_weights"].keys())
        active_cats = cal.get("active_categories", all_cats)

        preset = st.radio(
            "Category preset",
            ["All", "Critical only", "Custom"],
            index=0,
            key="ct_cat_preset",
            horizontal=True,
        )

        _CRITICAL = ["L2-Segmentation", "L3-Routing", "Edge-Port-Security", "AAA-Security"]

        if preset == "All":
            new_cats = all_cats
        elif preset == "Critical only":
            new_cats = _CRITICAL
            st.info(f"Critical: {', '.join(_CRITICAL)}")
        else:
            new_cats = []
            cols = st.columns(2)
            for i, cat in enumerate(all_cats):
                with cols[i % 2]:
                    weight = DEFAULT_CALIBRATION["category_weights"].get(cat, 1.0)
                    if st.checkbox(
                        f"{cat} (w={weight})",
                        value=cat in active_cats,
                        key=f"ct_cat_custom_{cat}",
                    ):
                        new_cats.append(cat)

        st.divider()

        # ── Apply ───────────────────────────────────────────────────────────
        if st.button("✅ Apply Quality Settings", use_container_width=True, key="ct_apply_quality"):
            st.session_state[_SK_CAL] = {
                **cal,
                "confidence_threshold": threshold,
                "strictness": strictness,
                "active_categories": new_cats,
            }
            st.success("Quality settings applied.")

        # ── Reset ───────────────────────────────────────────────────────────
        if st.button("↺ Reset to defaults", use_container_width=True, key="ct_reset_quality"):
            st.session_state[_SK_CAL] = dict(DEFAULT_CALIBRATION)
            st.rerun()

        # ── Summary ─────────────────────────────────────────────────────────
        st.caption(
            f"Current: threshold={threshold}% · {strictness} · "
            f"{len(new_cats)}/{len(all_cats)} categories active"
        )


def _threshold_advice(t: int):
    if t >= 85:
        st.warning("High bar — use for production-critical migrations. May flag minor gaps.")
    elif t >= 70:
        st.success("Recommended for standard migrations. Catches meaningful translation gaps.")
    elif t >= 60:
        st.info("Relaxed threshold. Good for exploratory review or early-stage testing.")
    else:
        st.warning("Very low threshold — only catches major failures. Not recommended for production.")


def _strictness_advice(s: str):
    if s == "strict":
        st.warning("Strict: requires exact EXOS syntax. May flag valid functional translations.")
    elif s == "balanced":
        st.success("Balanced: functional equivalence counts. Recommended for most migrations.")
    else:
        st.info("Lenient: passes if overall topology and reachability are preserved.")
