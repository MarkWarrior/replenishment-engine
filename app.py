"""
Streamlit 主应用入口
运行：streamlit run app.py  或 双击 start.bat 一键启动
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# 启动后端（如果还没运行）
# ============================================================
def ensure_backend_running():
    """检查并启动 FastAPI 后端，确保 API 可用"""
    try:
        import requests
        r = requests.get("http://localhost:8000/health", timeout=1)
        if r.status_code == 200:
            return  # 后端已运行
    except:
        pass
    
    # 后端没运行，启动它
    import subprocess
    import threading
    
    def start_server():
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--log-level", "warning"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    thread = threading.Thread(target=start_server, daemon=True)
    thread.start()
    
    # 等待后端启动
    import time
    for _ in range(10):
        time.sleep(1)
        try:
            r = requests.get("http://localhost:8000/health", timeout=1)
            if r.status_code == 200:
                return
        except:
            continue

ensure_backend_running()

# ============================================================
# 页面配置（必须在最前面）
# ============================================================
st.set_page_config(
    page_title="智能补货引擎",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 认证
from app.auth_ui import require_auth, logout, get_auth_header
tenant_id = require_auth()

# 侧边栏导航
st.sidebar.title("📦 智能补货引擎")
st.sidebar.markdown(f"**账户：** `{tenant_id}`")
st.sidebar.page_link("app.py", label="🏠 Dashboard", icon="🏠")
st.sidebar.page_link("pages/01_calculator.py", label="🧮 补货计算器", icon="🧮")
st.sidebar.page_link("pages/02_sku_manager.py", label="📋 SKU管理", icon="📋")
st.sidebar.page_link("pages/03_sales_manager.py", label="📈 销量管理", icon="📈")
st.sidebar.page_link("pages/04_replenishment_history.py", label="📋 补货历史", icon="📋")

st.sidebar.divider()

# 登出按钮
st.sidebar.button("🚪 退出登录", on_click=logout, use_container_width=True)

st.sidebar.caption("v0.2.0 · 公测版")