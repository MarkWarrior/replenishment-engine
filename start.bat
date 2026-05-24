@echo off
chcp 65001 >nul 2>&1
title 智能补货引擎 v0.2.0

echo.
echo  ╔═══════════════════════════════════════════════╗
echo  ║        智能补货引擎 v0.2.0 启动中...          ║
echo  ╚═══════════════════════════════════════════════╝
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.11+
    echo 下载地址：https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM 检查依赖
echo [1/3] 检查依赖...
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo [提示] 首次运行，正在安装依赖...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络
        pause
        exit /b 1
    )
)

REM 启动 FastAPI 后端
echo [2/3] 启动后端服务...
start /b python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning >nul 2>&1

REM 等待后端启动
echo       等待服务启动...
timeout /t 3 /nobreak >nul 2>&1

REM 检查后端是否启动成功
python -c "import requests; r=requests.get('http://localhost:8000/health',timeout=2)" >nul 2>&1
if errorlevel 1 (
    echo [警告] 后端服务启动可能有问题，继续尝试...
)

REM 启动 Streamlit 前端
echo [3/3] 启动前端界面...
echo.
echo ═══════════════════════════════════════════════════
echo   启动成功！正在打开浏览器...
echo   如果浏览器没有自动打开，请手动访问：
echo   http://localhost:8501
echo ═══════════════════════════════════════════════════
echo.

start http://localhost:8501
python -m streamlit run app.py --server.port 8501

pause