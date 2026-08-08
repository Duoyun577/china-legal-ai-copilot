"""Family-only authentication and stable user identities."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Mapping

import streamlit as st

from config.settings import settings


LOCAL_USER_ID = "local"


@dataclass(frozen=True)
class UserContext:
    user_id: str
    email: str
    name: str
    is_admin: bool = False
    authenticated: bool = False


def user_id_for_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized:
        raise ValueError("用户邮箱不能为空。")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def user_from_claims(claims: Mapping[str, Any]) -> UserContext | None:
    email = str(claims.get("email", "")).strip().lower()
    if not email:
        return None
    expires_at = claims.get("exp")
    if expires_at is not None:
        try:
            if int(expires_at) <= int(time.time()):
                return None
        except (TypeError, ValueError):
            return None
    allowed = settings.allowed_user_emails
    if not allowed or email not in allowed:
        return None
    return UserContext(
        user_id=user_id_for_email(email),
        email=email,
        name=str(claims.get("name") or email.split("@", 1)[0]),
        is_admin=email in settings.admin_user_emails,
        authenticated=True,
    )


def local_user() -> UserContext:
    return UserContext(LOCAL_USER_ID, "local@localhost", "本地用户", True, False)


def current_user() -> UserContext | None:
    if not settings.family_auth_enabled:
        return local_user()
    try:
        if not st.user.is_logged_in:
            return None
        return user_from_claims(st.user.to_dict())
    except (AttributeError, KeyError, RuntimeError):
        return None


def auth_configuration_available() -> bool:
    try:
        return "auth" in st.secrets
    except (FileNotFoundError, RuntimeError):
        return False


def require_user() -> UserContext:
    user = current_user()
    if user is not None:
        return user

    st.title("China Legal AI Copilot")
    try:
        logged_in = bool(st.user.is_logged_in)
    except (AttributeError, RuntimeError):
        logged_in = False

    if logged_in:
        st.error("当前账号不在家庭成员白名单中。")
        st.button("退出账号", on_click=st.logout, use_container_width=True)
    elif not auth_configuration_available():
        st.error("登录已启用，但尚未配置 Streamlit OIDC 密钥。请联系管理员。")
    else:
        st.info("本网站仅供获授权的家庭成员使用，请登录后继续。")
        st.button("使用 Google 登录", on_click=st.login, type="primary", use_container_width=True)
    st.stop()
    raise RuntimeError("st.stop() did not stop execution")


def render_user_controls(user: UserContext) -> None:
    if not settings.family_auth_enabled:
        st.sidebar.caption("本地兼容模式（登录尚未启用）")
        return
    st.sidebar.caption(f"已登录：{user.name}（{user.email}）")
    st.sidebar.button("退出登录", on_click=st.logout, use_container_width=True)
