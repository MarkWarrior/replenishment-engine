FROM python:3.11-slim

WORKDIR /app

# 预装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 数据目录（容器内持久化）
VOLUME ["/app/data"]

# 环境变量
ENV JWT_SECRET="replenishment-engine-mvp-secret"
ENV TOKEN_EXPIRE_HOURS=720

# 端口
EXPOSE 8000 8501

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# 启动脚本
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 &>/dev/null & streamlit run app.py --server.address 0.0.0.0 --server.port 8501"]