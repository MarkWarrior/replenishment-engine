"""
FastAPI 主应用
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import sku, inventory, replenishment, replenishment_record, sales
from app.auth import router as auth_router

app = FastAPI(
    title="智能补货决策引擎 API",
    description="跨境电商亚马逊卖家智能补货计算工具",
    version="0.1.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（开发环境）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router, tags=["认证"])
app.include_router(sku.router, prefix="/api/skus", tags=["SKU管理"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["库存管理"])
app.include_router(replenishment.router, prefix="/api/replenishment", tags=["补货计算"])
app.include_router(replenishment_record.router, prefix="/api/replenishment", tags=["补货记录"])
app.include_router(sales.router, prefix="/api/sales", tags=["销量管理"])


# 健康检查端点
@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/")
def root():
    return {"message": "智能补货决策引擎 API", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}