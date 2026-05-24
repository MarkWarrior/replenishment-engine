#!/bin/bash

# ============================================================
# 智能补货引擎 v0.2.0 启动脚本
# 使用方法：./start.sh
# 或双击 start.bat（Windows）
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        智能补货引擎 v0.2.0 启动中...        ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════╝${NC}"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo -e "${RED}[错误] 未检测到 Python，请先安装 Python 3.11+${NC}"
    echo "下载地址：https://www.python.org/downloads/"
    exit 1
fi

PYTHON_CMD=$(command -v python3 || command -v python)

# 检查依赖
echo -e "[1/3] ${YELLOW}检查依赖...${NC}"
if ! $PYTHON_CMD -m pip show streamlit > /dev/null 2>&1; then
    echo -e "[提示] 首次运行，正在安装依赖..."
    $PYTHON_CMD -m pip install -r requirements.txt
fi

# 启动 FastAPI 后端
echo -e "[2/3] ${YELLOW}启动后端服务...${NC}"
$PYTHON_CMD -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning > /dev/null 2>&1 &
BACKEND_PID=$!

# 等待后端启动
echo "       等待服务启动..."
sleep 3

# 检查后端是否启动成功
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "[警告] 后端服务启动可能有问题，继续尝试..."
fi

# 启动 Streamlit 前端
echo -e "[3/3] ${YELLOW}启动前端界面...${NC}"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  启动成功！正在打开浏览器...${NC}"
echo -e "${GREEN}  如果浏览器没有自动打开，请手动访问：${NC}"
echo -e "${GREEN}  → http://localhost:8501${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""

# 尝试自动打开浏览器
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8501
elif command -v open &> /dev/null; then
    open http://localhost:8501
fi

# 启动 Streamlit
exec $PYTHON_CMD -m streamlit run app.py --server.port 8501