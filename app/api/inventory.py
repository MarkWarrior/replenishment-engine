"""
库存管理 API路由（多租户版）
POST   /api/inventory/{sku_code}              # 录入库存
GET    /api/inventory/{sku_code}              # 获取库存
GET    /api/inventory/{sku_code}/history      # 获取历史库存
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.models.database import SKU, Inventory, SalesRecord, TenantDB
from app.auth import get_current_tenant

router = APIRouter()


# ============================================================
# Pydantic Schemas
# ============================================================

class InventoryCreate(BaseModel):
    current_stock: int
    in_transit_stock: int = 0
    notes: Optional[str] = None


class InventoryResponse(BaseModel):
    id: int
    sku_id: int
    sku_code: str
    record_date: datetime
    current_stock: int
    in_transit_stock: int
    days_cover: float
    notes: Optional[str]

    class Config:
        from_attributes = True


class InventoryHistoryResponse(BaseModel):
    records: List[InventoryResponse]
    total_count: int


# ============================================================
# 工具函数
# ============================================================

def calculate_days_cover(current_stock: int, avg_daily_sales: float) -> float:
    if avg_daily_sales <= 0:
        return 999.0
    return current_stock / avg_daily_sales


# ============================================================
# 路由（全部 tenant-aware）
# ============================================================

@router.post("/{sku_code}", response_model=InventoryResponse, status_code=201)
def create_inventory_record(sku_code: str, data: InventoryCreate,
                           tenant_id: str = Depends(get_current_tenant)):
    """录入库存快照"""
    session = TenantDB.get_session(tenant_id)
    try:
        sku = session.query(SKU).filter_by(sku_code=sku_code, is_active=True).first()
        if not sku:
            raise HTTPException(status_code=404, detail=f"SKU {sku_code} 不存在")

        # 计算日均销量
        thirty_days_ago = datetime.now() - timedelta(days=30)
        sales_records = session.query(SalesRecord).filter(
            SalesRecord.sku_id == sku.id,
            SalesRecord.sale_date >= thirty_days_ago,
        ).all()

        avg_sales = sum(r.quantity_sold for r in sales_records) / len(sales_records) if sales_records else 0.0
        days_cover = calculate_days_cover(data.current_stock, avg_sales)

        record = Inventory(
            sku_id=sku.id,
            current_stock=data.current_stock,
            in_transit_stock=data.in_transit_stock,
            days_cover=days_cover,
            notes=data.notes,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        return InventoryResponse(
            id=record.id, sku_id=record.sku_id, sku_code=sku_code,
            record_date=record.record_date, current_stock=record.current_stock,
            in_transit_stock=record.in_transit_stock, days_cover=record.days_cover,
            notes=record.notes,
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{sku_code}", response_model=InventoryResponse)
def get_current_inventory(sku_code: str, tenant_id: str = Depends(get_current_tenant)):
    """获取最新库存数据"""
    session = TenantDB.get_session(tenant_id)
    try:
        sku = session.query(SKU).filter_by(sku_code=sku_code, is_active=True).first()
        if not sku:
            raise HTTPException(status_code=404, detail=f"SKU {sku_code} 不存在")

        record = session.query(Inventory).filter_by(sku_id=sku.id).order_by(
            Inventory.record_date.desc()
        ).first()

        if not record:
            raise HTTPException(status_code=404, detail=f"SKU {sku_code} 暂无库存记录")

        return InventoryResponse(
            id=record.id, sku_id=record.sku_id, sku_code=sku_code,
            record_date=record.record_date, current_stock=record.current_stock,
            in_transit_stock=record.in_transit_stock, days_cover=record.days_cover,
            notes=record.notes,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{sku_code}/history", response_model=InventoryHistoryResponse)
def get_inventory_history(
    sku_code: str,
    limit: int = 30,
    offset: int = 0,
    tenant_id: str = Depends(get_current_tenant),
):
    """获取库存历史记录"""
    session = TenantDB.get_session(tenant_id)
    try:
        sku = session.query(SKU).filter_by(sku_code=sku_code, is_active=True).first()
        if not sku:
            raise HTTPException(status_code=404, detail=f"SKU {sku_code} 不存在")

        query = session.query(Inventory).filter_by(sku_id=sku.id)
        total_count = query.count()

        records = query.order_by(Inventory.record_date.desc()).offset(offset).limit(limit).all()

        return InventoryHistoryResponse(
            records=[
                InventoryResponse(
                    id=r.id, sku_id=r.sku_id, sku_code=sku_code,
                    record_date=r.record_date, current_stock=r.current_stock,
                    in_transit_stock=r.in_transit_stock, days_cover=r.days_cover,
                    notes=r.notes,
                )
                for r in records
            ],
            total_count=total_count,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()