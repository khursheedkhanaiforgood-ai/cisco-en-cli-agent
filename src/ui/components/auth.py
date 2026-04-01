"""
Simple session-based login for the CLI Mapping Agent.
Credentials are loaded from environment variables ONLY — never hardcoded.

Environment variables (set in Railway or .env):
    APP_USERS = JSON string, e.g.:
    '{"admin": {"password": "REDACTED_PASS", "role": "admin"}, "babla": {"password": "REDACTED_PASS", "role": "superadmin"}}'

    APP_REQUIRE_LOGIN = "true" | "false" (default: false — no login needed locally)
"""
import os
import json
import hashlib
import streamlit as st


def _load_users() -> dict:
    """Load users from APP_USERS env var. Returns {} if not set."""
    raw = os.environ.get("APP_USERS", "")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def login_required() -> bool:
    """Returns True if login is required (APP_REQUIRE_LOGIN=true in env)."""
    return os.environ.get("APP_REQUIRE_LOGIN", "false").lower() == "true"


def get_current_user() -> dict | None:
    """Returns current user dict {username, role} or None if not logged in."""
    return st.session_state.get("_auth_user")


def is_admin() -> bool:
    user = get_current_user()
    return user is not None and user.get("role") in ("admin", "superadmin")


def logout():
    st.session_state.pop("_auth_user", None)


def render_login_gate() -> bool:
    """
    Renders the login page if login is required and user is not authenticated.
    Returns True if the app should proceed (user is logged in or login not required).
    Returns False if the login page was rendered (app should stop).
    """
    if not login_required():
        return True  # no gate — proceed normally

    user = get_current_user()
    if user:
        return True  # already logged in

    # ── Login UI ──────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .login-wrap { max-width: 380px; margin: 80px auto; }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("## 🔀 CISCO ↔ EN CLI Agent")
            st.markdown("*Sign in to continue*")
            st.divider()

            username = st.text_input("Username", placeholder="username")
            password = st.text_input("Password", type="password", placeholder="password")
            login_btn = st.button("Sign in", use_container_width=True, type="primary")

            if login_btn:
                users = _load_users()
                if not users:
                    st.error("No users configured. Set APP_USERS environment variable.")
                elif username in users and users[username]["password"] == password:
                    st.session_state["_auth_user"] = {
                        "username": username,
                        "role": users[username].get("role", "user"),
                    }
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

    return False  # login page rendered — stop app rendering


def render_user_badge():
    """Renders a small user/logout widget for the sidebar."""
    user = get_current_user()
    if not user:
        return
    role_color = "#3fb950" if user["role"] == "superadmin" else "#58a6ff"
    st.sidebar.markdown(
        f"<span style='font-size:12px;color:{role_color}'>● {user['username']} "
        f"<span style='color:#8b949e'>({user['role']})</span></span>",
        unsafe_allow_html=True,
    )
    if st.sidebar.button("Sign out", use_container_width=True):
        logout()
        st.rerun()
