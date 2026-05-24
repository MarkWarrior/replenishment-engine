"""
补货记录 API路由（多租户版）
POST /api/replenishment/{sku_code}/save    # 保存补货决策
PUT  /api/replenishment/{id}/receive         # 标记已到货
GET  /api/replenishment/{sku_code}/history  # 获取补货历史
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.models.database import SKU, Replenishment, TenantDB
from app.auth import get_current_tenant

router = APIRouter()


# ============================================================
# Pydantic Schemas
# ============================================================

class SaveReplenishmentRequest(BaseModel):
    recommended_quantity: int
    mode: str
    shipping_method: str
    expected_arrival_days: int
    total_cost: float
    risk_score: int
    days_cover_at_order: float


class ReceiveReplenishmentRequest(BaseModel):
    quantity_received: int


class ReplenishmentResponse(BaseModel):
    id: int
    sku_id: int
    sku_code: str
    order_date: datetime
    expected_arrival_date: datetime
    actual_arrival_date: datetime | None = None
    quantity_ordered: int
    quantity_received: int
    total_cost: float
    mode: str
    status: str
    risk_score: int
    days_cover_at_order: float

    class Config:
        from_attributes = True


# ============================================================
# 路由（全部 tenant-aware）
# ============================================================

@router.post("/{sku_code}/save", response_model=ReplenishmentResponse, status_code=201)
def save_replenishment(sku_code: str, data: SaveReplenishmentRequest,
                      tenant_id: str = Depends(get_current_tenant)):
    """保存补货决策"""
    session = TenantDB.get_session(tenant_id)
    try:
        sku = session.query(SKU).filter_by(sku_code=sku_code, is_active=True).first()
        if not sku:
            raise HTTPException(status_code=404, detail=f"SKU {sku_code} 不存在")

        expected_arrival = datetime.now()
        if data.expected_arrival_days > 0:
            expected_arrival = datetime.now() + timedelta(days=data.expected_arrival_days)

        record = Replenishment(
            sku_id=sku.id,
            order_date=datetime.now(),
            expected_arrival_date=expected_arrival,
            quantity_ordered=data.recommended_quantity,
            quantity_received=0,
            total_cost=data.total_cost,
            mode=data.mode,
            status="pending",
            risk_score=data.risk_score,
            days_cover_at_order=data.days_cover_at_order,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        return ReplenishmentResponse(
            id=record.id, sku_id=record.sku_id, sku_code=sku_code,
            order_date=record.order_date,
            expected_arrival_date=record.expected_arrival_date,
            actual_arrival_date=record.actual_arrival_date,
            quantity_ordered=record.quantity_ordered,
            quantity_received=record.quantity_received,
            total_cost=record.total_cost, mode=record.mode,
            status=record.status, risk_score=record.risk_score,
            days_cover_at_order=record.days_cover_at_order,
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.put("/{record_id}/receive", response_model=ReplenishmentResponse)
def receive_replenishment(record_id: int, data: ReceiveReplenishmentRequest,
                         tenant_id: str = Depends(get_current_tenant)):
    """标记补货已到货"""
    session = TenantDB.get_session(tenant_id)
    try:
        record = session.query(Replenishment).get(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="补货记录不存在")

        record.quantity_received = data.quantity_received
        record.actual_arrival_date = datetime.now()
        record.status = "delivered"

        session.commit()
        session.refresh(record)

        return ReplenishmentResponse(
            id=record.id, sku_id=record.sku_id,
            sku_code=record.sku.sku_code if record.sku else "UNKNOWN",
            order_date=record.order_date,
            expected_arrival_date=record.expected_arrival_date,
            actual_arrival_date=record.actual_arrival_date,
            quantity_ordered=record.quantity_ordered,
            quantity_received=record.quantity_received,
            total_cost=record.total_cost, mode=record.mode,
            status=record.status, risk_score=record.risk_score,
            days_cover_at_order=record.days_cover_at_order,
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{sku_code}/history", response_model=List[ReplenishmentResponse])
def get_replenishment_history(sku_code: str, limit: int = 20,
                              tenant_id: str = Depends(get_current_tenant)):
    """获取SKU的补货历史记录"""
    session = TenantDB.get_session(tenant_id)
    try:
        sku = session.query(SKU).filter_by(sku_code=sku_code, is_active=True).first()
        if not sku:
            raise HTTPException(status_code=404, detail=f"SKU {sku_code} 不存在")

        records = session.query(Replenishment).filter_by(sku_id=sku.id).order_by(
            Replenishment.order_date.desc()
        ).limit(limit).all()

        return [
            ReplenishmentResponse(
                id=r.id, sku_id=r.sku_id, sku_code=sku_code,
                order_date=r.order_date,
                expected_arrival_date=r.expected_arrival_date,
                actual_arrival_date=r.actual_arrival_date,
                quantity_ordered=r.quantity_ordered,
                quantity_received=r.quantity_received,
                total_cost=r.total_cost, mode=r.mode,
                status=r.status, risk_score=r.risk_score,
                days_cover_at_order=r.days_cover_at_order,
            )
            for r in records
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()