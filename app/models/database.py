"""
多租户数据库模型
每个租户（用户）有独立的 SQLite 数据库文件，实现数据完全隔离

架构：
- 认证层：app/auth.py（JWT Bearer Token）
- 数据层：每个 tenant_id 对应 data/{tenant_id}.db
- 路由层：所有 API 通过 Depends(get_current_tenant) 注入 tenant_id

所有数据库操作必须通过 TenantDB.get_session(tenant_id) 获取会话
"""

import os
import threading
from typing import Optional
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()

# ============================================================
# 单租户模型（所有表共享 tenant_id 字段）
# ============================================================


class SKU(Base):
    """SKU模型"""
    __tablename__ = "skus"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_code = Column(String(64), nullable=False, index=True)
    asin = Column(String(20), nullable=True)
    product_name = Column(String(255), nullable=False)

    # 产品成本
    product_cost = Column(Float, default=0.0)
    freight_cost = Column(Float, default=0.0)
    fba_fee = Column(Float, default=0.0)
    selling_price = Column(Float, default=0.0)

    # 供应链参数
    lead_time_days = Column(Integer, default=30)
    supply_stability = Column(String(20), default="normal")

    # 配置
    min_stock_days = Column(Integer, default=7)
    safety_factor = Column(Float, default=1.15)

    # 状态
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    inventory_records = relationship("Inventory", back_populates="sku", cascade="all, delete-orphan")
    sales_records = relationship("SalesRecord", back_populates="sku", cascade="all, delete-orphan")
    replenishment_records = relationship("Replenishment", back_populates="sku", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SKU {self.sku_code}: {self.product_name}>"


class Inventory(Base):
    """库存快照模型"""
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False, index=True)
    record_date = Column(DateTime, default=datetime.utcnow, index=True)

    current_stock = Column(Integer, default=0)
    in_transit_stock = Column(Integer, default=0)
    days_cover = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)

    sku = relationship("SKU", back_populates="inventory_records")

    def __repr__(self):
        return f"<Inventory {self.sku_id} @ {self.record_date.date()}: {self.current_stock}>"


class SalesRecord(Base):
    """销量记录模型"""
    __tablename__ = "sales_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False, index=True)
    sale_date = Column(DateTime, default=datetime.utcnow, index=True)

    quantity_sold = Column(Integer, default=0)
    unit_price = Column(Float, default=0.0)

    sku = relationship("SKU", back_populates="sales_records")

    def __repr__(self):
        return f"<Sales {self.sku_id} @ {self.sale_date.date()}: {self.quantity_sold} units>"


class Replenishment(Base):
    """补货记录模型"""
    __tablename__ = "replenishments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False, index=True)

    order_date = Column(DateTime, default=datetime.utcnow, index=True)
    expected_arrival_date = Column(DateTime, nullable=True)
    actual_arrival_date = Column(DateTime, nullable=True)

    quantity_ordered = Column(Integer, default=0)
    quantity_received = Column(Integer, default=0)

    total_cost = Column(Float, default=0.0)

    mode = Column(String(20), default="standard")
    status = Column(String(20), default="pending")

    risk_score = Column(Integer, default=0)
    days_cover_at_order = Column(Float, default=0.0)

    sku = relationship("SKU", back_populates="replenishment_records")

    def __repr__(self):
        return f"<Replenishment {self.sku_id}: {self.quantity_ordered} units @ {self.order_date.date()}>"


# ============================================================
# 多租户数据库管理器
# ============================================================

class TenantDB:
    """
    多租户数据库管理器
    每个租户有独立的 SQLite 文件：data/{tenant_id}.db
    线程安全，使用 thread-local 存储引擎和会话
    """

    _engines: dict = {}  # tenant_id -> engine
    _sessions: dict = {}  # tenant_id -> sessionmaker
    _lock = threading.Lock()
    _data_dir = "data"

    @classmethod
    def _get_db_path(cls, tenant_id: str) -> str:
        """获取租户数据库文件路径"""
        os.makedirs(cls._data_dir, exist_ok=True)
        # tenant_id 用于文件名，但模型中不存储（每文件独立）
        safe_name = tenant_id.replace("/", "_").replace("\\", "_")
        return os.path.join(cls._data_dir, f"{safe_name}.db")

    @classmethod
    def _get_engine(cls, tenant_id: str):
        """获取或创建租户的数据库引擎（线程安全）"""
        if tenant_id not in cls._engines:
            with cls._lock:
                if tenant_id not in cls._engines:
                    db_path = cls._get_db_path(tenant_id)
                    engine = create_engine(
                        f"sqlite:///{db_path}",
                        echo=False,
                        connect_args={"check_same_thread": False},
                    )
                    # 确保表已创建
                    Base.metadata.create_all(engine)
                    cls._engines[tenant_id] = engine
        return cls._engines[tenant_id]

    @classmethod
    def get_session(cls, tenant_id: str):
        """获取当前租户的数据库会话"""
        engine = cls._get_engine(tenant_id)
        Session = sessionmaker(bind=engine)
        return Session()

    @classmethod
    def create_tables(cls, tenant_id: str):
        """为租户创建表"""
        engine = cls._get_engine(tenant_id)
        Base.metadata.create_all(engine)

    @classmethod
    def reset_engine(cls, tenant_id: str):
        """重置引擎（用于数据库迁移）"""
        if tenant_id in cls._engines:
            with cls._lock:
                if tenant_id in cls._engines:
                    cls._engines[tenant_id].dispose()
                    del cls._engines[tenant_id]


# ============================================================
# 兼容性别名（单租户场景下直接调用）
# ============================================================

def get_engine(db_path: str = "replenishment.db"):
    """获取引擎（保留兼容性）"""
    return TenantDB._get_engine("default")

def create_tables(engine):
    """创建所有表"""
    Base.metadata.create_all(engine)

def get_session(engine=None):
    """获取会话（保留兼容性，内部租户隔离由路由层处理）"""
    return TenantDB.get_session("default")

def init_sample_data(session):
    """初始化示例数据"""
    from datetime import datetime, timedelta

    sku1 = SKU(
        sku_code="CATIT-FILTER-12",
        asin="B08XXXXXXX",
        product_name="Catit兼容滤芯12个装",
        product_cost=2.20,
        freight_cost=0.60,
        fba_fee=3.80,
        selling_price=13.99,
        lead_time_days=25,
        supply_stability="normal",
    )
    session.add(sku1)

    sku2 = SKU(
        sku_code="CATIT-FILTER-24",
        asin="B08YYYYYYY",
        product_name="Catit兼容滤芯24个装大容量版",
        product_cost=4.00,
        freight_cost=1.00,
        fba_fee=4.20,
        selling_price=26.99,
        lead_time_days=25,
        supply_stability="stable",
    )
    session.add(sku2)

    session.commit()

    # 添加30天销量
    today = datetime.now()
    for i in range(30):
        date = today - timedelta(days=30 - i)
        session.add(SalesRecord(
            sku_id=sku1.id,
            sale_date=date,
            quantity_sold=25 + (i % 10 - 5),
            unit_price=13.99,
        ))
        session.add(SalesRecord(
            sku_id=sku2.id,
            sale_date=date,
            quantity_sold=15 + (i % 7 - 3),
            unit_price=26.99,
        ))

    # 添加当前库存
    session.add(Inventory(
        sku_id=sku1.id,
        record_date=today,
        current_stock=120,
        in_transit_stock=500,
        days_cover=4.8,
    ))
    session.add(Inventory(
        sku_id=sku2.id,
        record_date=today,
        current_stock=80,
        in_transit_stock=0,
        days_cover=5.3,
    ))

    session.commit()
    print(f"示例数据已初始化：2个SKU，30天销量记录，2条库存记录")