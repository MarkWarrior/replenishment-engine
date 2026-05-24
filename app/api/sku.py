"""
SKU管理 API路由（多租户版）
所有操作自动注入当前用户的 tenant_id，实现数据完全隔离
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.models.database import SKU, TenantDB
from app.auth import get_current_tenant
from app.core import SafetyCalculator

router = APIRouter()


# ============================================================
# Pydantic Schemas
# ============================================================

class SKUCreate(BaseModel):
    sku_code: str
    asin: Optional[str] = None
    product_name: str
    product_cost: float = 0.0
    freight_cost: float = 0.0
    fba_fee: float = 0.0
    selling_price: float = 0.0
    lead_time_days: int = 30
    supply_stability: str = "normal"
    min_stock_days: int = 7
    safety_factor: Optional[float] = None  # None=自动计算


class SKUUpdate(BaseModel):
    asin: Optional[str] = None
    product_name: Optional[str] = None
    product_cost: Optional[float] = None
    freight_cost: Optional[float] = None
    fba_fee: Optional[float] = None
    selling_price: Optional[float] = None
    lead_time_days: Optional[int] = None
    supply_stability: Optional[str] = None
    min_stock_days: Optional[int] = None
    safety_factor: Optional[float] = None


class SKUResponse(BaseModel):
    id: int
    tenant_id: str
    sku_code: str
    asin: Optional[str]
    product_name: str
    product_cost: float
    freight_cost: float
    fba_fee: float
    selling_price: float
    lead_time_days: int
    supply_stability: str
    min_stock_days: int
    safety_factor: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# 路由（全部 tenant-aware）
# ============================================================

@router.post("", response_model=SKUResponse, status_code=201)
def create_sku(data: SKUCreate, tenant_id: str = Depends(get_current_tenant)):
    """创建新SKU（自动关联当前用户）"""
    session = TenantDB.get_session(tenant_id)
    try:
        # 检查同tenant下是否已存在
        existing = session.query(SKU).filter_by(sku_code=data.sku_code).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"SKU {data.sku_code} 已存在")

        # 自动计算安全系数
        safety_calc = SafetyCalculator()
        auto_safety_factor = safety_calc.calculate(
            lead_time_days=data.lead_time_days,
            avg_lead_time_days=data.lead_time_days,
            supply_stability=data.supply_stability,
        ) if data.safety_factor is None else data.safety_factor

        sku = SKU(
            tenant_id=tenant_id,
            sku_code=data.sku_code,
            asin=data.asin,
            product_name=data.product_name,
            product_cost=data.product_cost,
            freight_cost=data.freight_cost,
            fba_fee=data.fba_fee,
            selling_price=data.selling_price,
            lead_time_days=data.lead_time_days,
            supply_stability=data.supply_stability,
            min_stock_days=data.min_stock_days,
            safety_factor=auto_safety_factor,
        )
        session.add(sku)
        session.commit()
        session.refresh(sku)
        return SKUResponse(
            id=sku.id, tenant_id=sku.tenant_id, sku_code=sku.sku_code,
            asin=sku.asin, product_name=sku.product_name,
            product_cost=sku.product_cost, freight_cost=sku.freight_cost,
            fba_fee=sku.fba_fee, selling_price=sku.selling_price,
            lead_time_days=sku.lead_time_days, supply_stability=sku.supply_stability,
            min_stock_days=sku.min_stock_days, safety_factor=sku.safety_factor,
            is_active=sku.is_active, created_at=sku.created_at, updated_at=sku.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("", response_model=List[SKUResponse])
def list_skus(is_active: Optional[bool] = None, tenant_id: str = Depends(get_current_tenant)):
    """获取当前用户的所有SKU列表"""
    session = TenantDB.get_session(tenant_id)
    try:
        query = session.query(SKU).filter_by(tenant_id=tenant_id)
        if is_active is not None:
            query = query.filter_by(is_active=is_active)
        skus = query.order_by(SKU.updated_at.desc()).all()
        return [
            SKUResponse(
                id=s.id, tenant_id=s.tenant_id, sku_code=s.sku_code,
                asin=s.asin, product_name=s.product_name,
                product_cost=s.product_cost, freight_cost=s.freight_cost,
                fba_fee=s.fba_fee, selling_price=s.selling_price,
                lead_time_days=s.lead_time_days, supply_stability=s.supply_stability,
                min_stock_days=s.min_stock_days, safety_factor=s.safety_factor,
                is_active=s.is_active, created_at=s.created_at, updated_at=s.updated_at,
            )
            for s in skus
        ]
    finally:
        session.close()


@router.get("/{sku_code}", response_model=SKUResponse)
def get_sku(sku_code: str, tenant_id: str = Depends(get_current_tenant)):
    """获取单个SKU"""
    session = TenantDB.get_session(tenant_id)
    try:
        sku = session.query(SKU).filter_by(sku_code=sku_code).first()
        if not sku:
            raise HTTPException(status_code=404, detail=f"SKU {sku_code} 不存在")
        return SKUResponse(
            id=sku.id, tenant_id=sku.tenant_id, sku_code=sku.sku_code,
            asin=sku.asin, product_name=sku.product_name,
            product_cost=sku.product_cost, freight_cost=sku.freight_cost,
            fba_fee=sku.fba_fee, selling_price=sku.selling_price,
            lead_time_days=sku.lead_time_days, supply_stability=sku.supply_stability,
            min_stock_days=sku.min_stock_days, safety_factor=sku.safety_factor,
            is_active=sku.is_active, created_at=sku.created_at, updated_at=sku.updated_at,
        )
    finally:
        session.close()


@router.put("/{sku_code}", response_model=SKUResponse)
def update_sku(sku_code: str, data: SKUUpdate, tenant_id: str = Depends(get_current_tenant)):
    """更新SKU"""
    session = TenantDB.get_session(tenant_id)
    try:
        sku = session.query(SKU).filter_by(sku_code=sku_code).first()
        if not sku:
            raise HTTPException(status_code=404, detail=f"SKU {sku_code} 不存在")

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(sku, field, value)

        session.commit()
        session.refresh(sku)
        return SKUResponse(
            id=sku.id, tenant_id=sku.tenant_id, sku_code=sku.sku_code,
            asin=sku.asin, product_name=sku.product_name,
            product_cost=sku.product_cost, freight_cost=sku.freight_cost,
            fba_fee=sku.fba_fee, selling_price=sku.selling_price,
            lead_time_days=sku.lead_time_days, supply_stability=sku.supply_stability,
            min_stock_days=sku.min_stock_days, safety_factor=sku.safety_factor,
            is_active=sku.is_active, created_at=sku.created_at, updated_at=sku.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/{sku_code}", status_code=204)
def delete_sku(sku_code: str, tenant_id: str = Depends(get_current_tenant)):
    """删除SKU（软删除）"""
    session = TenantDB.get_session(tenant_id)
    try:
        sku = session.query(SKU).filter_by(sku_code=sku_code).first()
        if not sku:
            raise HTTPException(status_code=404, detail=f"SKU {sku_code} 不存在")

        sku.is_active = False
        session.commit()
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()