"""Optional single-password gate for public deployments.

When ACCESS_PASSWORD is set, visitors must enter it once before the app renders.
The gate is OFF by default (empty password), so local/family usage is unchanged.
The unlocked flag lives in the browser session only; there is no cookie on disk.
"""
from __future__ import annotations

import hmac

import streamlit as st

from config.settings import settings

_SESSION_KEY = "_access_gate_unlocked"


def is_unlocked() -> bool:
    return bool(st.session_state.get(_SESSION_KEY, False))


def require_access_password() -> None:
    """Block rendering until the correct password is entered (if configured)."""
    password = settings.access_password
    if not password:
        return
    if st.session_state.get(_SESSION_KEY, False):
        return

    st.title("律师工作台 · 访问验证")
    st.info("本工作台仅供授权人员使用，请输入访问口令后继续。")
    entered = st.text_input("访问口令", type="password", key="_access_gate_input")
    if st.button("进入", type="primary"):
        if hmac.compare_digest(entered, password):
            st.session_state[_SESSION_KEY] = True
            st.rerun()
        else:
            st.error("口令不正确，请重试。")
    st.stop()
