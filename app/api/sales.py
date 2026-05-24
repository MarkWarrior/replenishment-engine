"""
销量历史导入 API路由（多租户版）
POST /api/sales/{sku_code}/import_csv   # CSV批量导入销量
GET  /api/sales/{sku_code}/history      # 获取销量历史
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from typing import List
from pydantic import BaseModel
from datetime import datetime, timedelta
import csv
import io

from app.models.database import SKU, SalesRecord, TenantDB
from app.auth import get_current_tenant

router = APIRouter()


# ============================================================
# Pydantic Schemas
# ============================================================

class SalesRecordResponse(BaseModel):
    id: int
    sku_id: int
    sku_code: str
    sale_date: datetime
    quantity_sold: int
    unit_price: float

    class Config:
        from_attributes = True


class ImportResult(BaseModel):
    success_count: int
    skip_count: int
    errors: List[str]


# ============================================================
# 路由（全部 tenant-aware）
# ============================================================

@router.post("/{sku_code}/import_csv", response_model=ImportResult, status_code=201)
async def import_sales_csv(
    sku_code: str,
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_current_tenant),
):
    """CSV批量导入销量历史"""
    session = TenantDB.get_session(tenant_id)
    try:
        sku = session.query(SKU).filter_by(sku_code=sku_code, is_active=True).first()
        if not sku:
            raise HTTPException(status_code=404, detail=f"SKU {sku_code} 不存在")

        content = await file.read()
        decoded = content.decode("utf-8-sig")

        reader = csv.DictReader(io.StringIO(decoded))
        success_count = 0
        skip_count = 0
        errors = []

        for i, row in enumerate(reader):
            try:
                date_str = row.get("date", "").strip()
                if not date_str:
                    errors.append(f"第{i+2}行：缺少日期字段")
                    skip_count += 1
                    continue

                sale_date = datetime.strptime(date_str, "%Y-%m-%d")
                quantity = int(float(row.get("quantity_sold", 0)))
                price = float(row.get("unit_price", 0)) if row.get("unit_price") else 0.0

                existing = session.query(SalesRecord).filter_by(
                    sku_id=sku.id, sale_date=sale_date
                ).first()
                if existing:
                    skip_count += 1
                    continue

                record = SalesRecord(
                    sku_id=sku.id,
                    sale_date=sale_date,
                    quantity_sold=quantity,
                    unit_price=price,
                )
                session.add(record)
                success_count += 1

            except ValueError as e:
                errors.append(f"第{i+2}行：数据格式错误 - {str(e)}")
                skip_count += 1
            except Exception as e:
                errors.append(f"第{i+2}行：{str(e)}")
                skip_count += 1

        session.commit()

        return ImportResult(
            success_count=success_count,
            skip_count=skip_count,
            errors=errors[:20],
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{sku_code}/history", response_model=List[SalesRecordResponse])
def get_sales_history(
    sku_code: str,
    days: int = 30,
    offset: int = 0,
    limit: int = 100,
    tenant_id: str = Depends(get_current_tenant),
):
    """获取SKU的销量历史"""
    session = TenantDB.get_session(tenant_id)
    try:
        sku = session.query(SKU).filter_by(sku_code=sku_code, is_active=True).first()
        if not sku:
            raise HTTPException(status_code=404, detail=f"SKU {sku_code} 不存在")

        start_date = datetime.now() - timedelta(days=days)

        records = session.query(SalesRecord).filter(
            SalesRecord.sku_id == sku.id,
            SalesRecord.sale_date >= start_date,
        ).order_by(SalesRecord.sale_date.desc()).offset(offset).limit(limit).all()

        return [
            SalesRecordResponse(
                id=r.id, sku_id=r.sku_id, sku_code=sku_code,
                sale_date=r.sale_date, quantity_sold=r.quantity_sold,
                unit_price=r.unit_price,
            )
            for r in records
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()