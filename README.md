# 📦 智能补货引擎 v0.2.0

> 跨境电商亚马逊卖家智能补货计算工具 · 公测版

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 🎯 产品简介

智能补货引擎帮助亚马逊卖家自动计算最优补货量，避免断货或库存积压。

**核心功能：**
- 🧮 **智能补货计算**：基于日均销量、备货天数、补货周期自动计算推荐补货量
- 📋 **SKU 管理**：批量管理商品，追踪库存变化
- 📈 **销量追踪**：记录每日销量，自动计算日均销量
- 📋 **补货历史**：记录每次补货决策，方便复盘

---

## 🚀 快速开始

### Windows 用户（推荐）

1. **下载代码**：点击页面右上角 `Code` → `Download ZIP` → 解压到桌面

2. **双击启动**：双击 `start.bat` 文件

3. **开始使用**：浏览器自动打开，访问 http://localhost:8501

### Mac / Linux 用户

1. **下载代码**：点击页面右上角 `Code` → `Download ZIP` → 解压到桌面

2. **打开终端**：
   - Mac：按 `Command + 空格`，搜索"终端"，回车
   - Linux：按 `Ctrl + Alt + T`

3. **进入目录**（把 `Downloads` 换成你实际的下载路径）：
   ```bash
   cd ~/Downloads/replenishment-engine
   chmod +x start.sh
   ./start.sh
   ```

4. **开始使用**：浏览器自动打开，访问 http://localhost:8501

---

## 📋 详细安装步骤（首次使用）

### Step 1：安装 Python

1. 打开 https://www.python.org/downloads/
2. 下载 Python 3.11 或更高版本
3. 运行安装包
4. ⚠️ **重要**：**勾选"Add Python to PATH"**（必须打勾！）
5. 点击 "Install Now"

验证是否安装成功：
- Windows：按 `Win + R`，输入 `cmd`，回车。输入 `python --version`，回车
- Mac：打开终端，输入 `python3 --version`，回车

### Step 2：安装依赖

**Windows：**
1. 按 `Win + R`，输入 `cmd`，回车
2. 进入项目目录（把路径换成你实际的）：
   ```bash
   cd %USERPROFILE%\Desktop\replenishment-engine
   ```
3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

**Mac：**
1. 打开终端
2. 进入项目目录：
   ```bash
   cd ~/Downloads/replenishment-engine
   ```
3. 安装依赖：
   ```bash
   pip3 install -r requirements.txt
   ```

### Step 3：启动程序

**方式一：一键启动（推荐）**
```bash
# Windows：双击 start.bat
# Mac/Linux：运行 ./start.sh
```

**方式二：手动启动**
```bash
# 终端 1：启动后端
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 终端 2：启动前端（另开一个终端窗口）
streamlit run app.py --server.port 8501
```

---

## 📖 使用教程

### 首次注册

1. 打开程序后，会看到登录界面
2. 输入一个用户名（只能用英文字母和数字，比如 `xiaoming`）
3. 输入密码（至少 6 位）
4. 点击"注册"
5. 注册后，用同样的用户名和密码登录

### 添加商品（SKU）

1. 点击左侧菜单 **"📋 SKU管理"**
2. 点击 **"添加 SKU"**
3. 填写商品信息：
   - **SKU 名称**：给商品起个名字，比如 "猫饮水机滤芯 12个装"
   - **日均销量**：每天平均卖几个
   - **当前库存**：仓库里现在有几个
   - **备货天数**：你想留多少天的库存（填 7-14）
   - **补货周期**：从下单到收货要几天（填 7-14）

### 计算补货

1. 点击左侧菜单 **"🧮 补货计算器"**
2. 选择你要计算的 SKU
3. 点击 **"计算补货量"**
4. 查看推荐结果：
   - 📊 **推荐补货数量**
   - 📅 **建议下单日期**
   - ⚠️ **库存警告**（如果库存过低会显示红色）

---

## ❓ 常见问题

### Q：提示 "Python 不是内部命令"
**A**：Python 没有安装好，或没有勾选 "Add Python to PATH"。
重新运行 Python 安装程序，这次记得打勾。

### Q：提示 "Module not found"
**A**：依赖没有安装。运行：
```bash
pip install -r requirements.txt
```

### Q：浏览器打不开
**A**：手动打开浏览器，在地址栏输入 `http://localhost:8501`，回车。

### Q：忘记密码怎么办
**A**：删除项目目录下的 `replenishment.db` 文件，重新打开程序注册。

### Q：启动后显示空白页面
**A**：等待 10 秒刷新页面，或重启程序（关掉窗口，重新双击 start.bat）。

---

## 🔒 数据说明

**你的数据完全私密：**
- 所有数据存储在你自己的电脑里
- 不会上传到任何云服务器
- 不会发送到任何第三方

**数据文件位置：** `replenishment.db`（SQLite 数据库）

---

## 🛠 技术架构

```
┌─────────────────────────────────────────┐
│  Streamlit 前端（用户界面）              │
│  http://localhost:8501                  │
└─────────────────┬───────────────────────┘
                  │ HTTP API
┌─────────────────▼───────────────────────┐
│  FastAPI 后端（业务逻辑）                │
│  http://localhost:8000                  │
└─────────────────┬───────────────────────┘
                  │ SQL
┌─────────────────▼───────────────────────┐
│  SQLite 数据库（本地存储）               │
│  replenishment.db                       │
└─────────────────────────────────────────┘
```

**技术栈：**
- 前端：Streamlit + Plotly
- 后端：FastAPI + SQLAlchemy
- 数据库：SQLite
- 语言：Python 3.11+

---

## 📁 项目结构

```
replenishment-engine/
├── app.py              # 程序入口
├── app/
│   ├── main.py         # FastAPI 后端
│   ├── auth.py         # 认证逻辑
│   ├── auth_ui.py      # 认证 UI
│   └── api/            # API 路由
├── pages/              # Streamlit 页面
│   ├── 01_calculator.py
│   ├── 02_sku_manager.py
│   ├── 03_sales_manager.py
│   └── 04_replenishment_history.py
├── tests/              # 单元测试
├── requirements.txt    # Python 依赖
├── start.bat           # Windows 一键启动
├── start.sh            # Mac/Linux 启动脚本
└── .gitignore          # Git 忽略文件
```

---

## 🤝 反馈与支持

遇到问题？欢迎提交 Issue！

---

## 📝 更新日志

### v0.2.0（公测版）
- ✅ 补货算法核心功能
- ✅ 多租户认证系统
- ✅ SKU 管理
- ✅ 销量追踪
- ✅ 补货历史记录
- ✅ 一键启动脚本