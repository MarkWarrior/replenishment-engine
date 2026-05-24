"""
Streamlit 认证工具
在每个页面开头调用 auth.require_auth() 即可完成鉴权
"""

import streamlit as st
import requests
import time

API_BASE = "http://localhost:8000"


def init_auth_state():
    """初始化 session_state 中的认证相关字段"""
    defaults = {
        "auth_token": None,
        "tenant_id": None,
        "token_exp": None,
        "logged_in": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def require_auth():
    """
    每个页面的第一个调用。
    检测是否已登录，未登录则显示登录界面并阻塞。
    已登录则返回 tenant_id。
    """
    init_auth_state()
    return _render_auth_ui()


def _render_auth_ui():
    """渲染认证 UI 并处理登录/注册逻辑"""

    # 检测 token 是否过期
    if st.session_state.logged_in and st.session_state.token_exp:
        if time.time() > st.session_state.token_exp:
            _logout()
            st.rerun()

    if st.session_state.logged_in:
        return st.session_state.tenant_id

    # 未登录 → 显示登录注册界面（占满全屏）
    st.set_page_config(page_title="登录 - 智能补货引擎", page_icon="📦")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.divider()
        st.title("🔐 智能补货引擎")
        st.caption("请先登录或注册账户")

        tab_login, tab_register = st.tabs(["登录", "注册"])

        with tab_login:
            login_tenant = st.text_input("账户名（tenant_id）", placeholder="例如: my_shop_001", key="login_tenant")
            login_pwd = st.text_input("密码", type="password", key="login_pwd")

            if st.button("登录", type="primary", use_container_width=True):
                if not login_tenant or not login_pwd:
                    st.error("请填写账户名和密码")
                else:
                    with st.spinner("登录中..."):
                        try:
                            r = requests.post(
                                f"{API_BASE}/auth/login",
                                json={"tenant_id": login_tenant, "password": login_pwd},
                                timeout=10,
                            )
                            if r.status_code == 200:
                                data = r.json()
                                st.session_state.auth_token = data["access_token"]
                                st.session_state.tenant_id = data["tenant_id"]
                                st.session_state.logged_in = True
                                st.session_state.token_exp = time.time() + 30 * 24 * 3600
                                st.success("登录成功！")
                                st.rerun()
                            else:
                                st.error(f"登录失败：{r.json().get('detail', r.text)}")
                        except Exception as e:
                            st.error(f"连接失败：{e}")

        with tab_register:
            reg_tenant = st.text_input("账户名（tenant_id）", placeholder="字母/数字/下划线，唯一标识", key="reg_tenant")
            reg_pwd = st.text_input("密码", type="password", key="reg_pwd")
            reg_pwd2 = st.text_input("确认密码", type="password", key="reg_pwd2")

            if st.button("注册", type="primary", use_container_width=True):
                if not reg_tenant or not reg_pwd:
                    st.error("请填写账户名和密码")
                elif reg_pwd != reg_pwd2:
                    st.error("两次密码不一致")
                elif len(reg_pwd) < 6:
                    st.error("密码至少6位")
                else:
                    with st.spinner("注册中..."):
                        try:
                            rr = requests.post(
                                f"{API_BASE}/auth/register",
                                json={"tenant_id": reg_tenant, "password": reg_pwd},
                                timeout=10,
                            )
                            if rr.status_code == 201:
                                st.success("注册成功！请在左侧登录")
                                st.info("提示：注册后系统会自动登录")
                                # 自动登录
                                r2 = requests.post(
                                    f"{API_BASE}/auth/login",
                                    json={"tenant_id": reg_tenant, "password": reg_pwd},
                                    timeout=10,
                                )
                                if r2.status_code == 200:
                                    data = r2.json()
                                    st.session_state.auth_token = data["access_token"]
                                    st.session_state.tenant_id = data["tenant_id"]
                                    st.session_state.logged_in = True
                                    st.session_state.token_exp = time.time() + 30 * 24 * 3600
                                    st.rerun()
                            else:
                                detail = rr.json().get("detail", rr.text)
                                st.error(f"注册失败：{detail}")
                        except Exception as e:
                            st.error(f"连接失败：{e}")

        st.divider()
        st.caption("公测版 · 数据完全隔离")

    st.stop()  # 未登录时终止页面渲染


def _logout():
    st.session_state.auth_token = None
    st.session_state.tenant_id = None
    st.session_state.logged_in = False
    st.session_state.token_exp = None


def logout():
    """手动登出"""
    _logout()
    st.rerun()


def get_auth_header():
    """获取当前用户的 Authorization header"""
    if st.session_state.auth_token:
        return {"Authorization": f"Bearer {st.session_state.auth_token}"}
    return {}


def api_get(path: str, **kwargs):
    """携带 Token 的 GET 请求"""
    kwargs.setdefault("timeout", 10)
    return requests.get(f"{API_BASE}{path}", headers=get_auth_header(), **kwargs)


def api_post(path: str, **kwargs):
    """携带 Token 的 POST 请求"""
    kwargs.setdefault("timeout", 10)
    return requests.post(f"{API_BASE}{path}", headers=get_auth_header(), **kwargs)


def api_put(path: str, **kwargs):
    """携带 Token 的 PUT 请求"""
    kwargs.setdefault("timeout", 10)
    return requests.put(f"{API_BASE}{path}", headers=get_auth_header(), **kwargs)


def api_delete(path: str, **kwargs):
    """携带 Token 的 DELETE 请求"""
    kwargs.setdefault("timeout", 10)
    return requests.delete(f"{API_BASE}{path}", headers=get_auth_header(), **kwargs)


def api_post_files(path: str, files: dict, **kwargs):
    """携带 Token 的 multipart POST 请求（用于文件上传）"""
    kwargs.setdefault("timeout", 30)
    return requests.post(f"{API_BASE}{path}", headers=get_auth_header(), files=files, **kwargs)