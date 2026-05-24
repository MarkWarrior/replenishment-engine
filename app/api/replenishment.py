"""
补货计算 API路由
POST /api/replenishment/calculate    # 计算补货建议
POST /api/replenishment/batch         # 批量计算
GET  /api/replenishment/{sku_code}   # 获取最近补货记录
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.models.database import SKU, Inventory, SalesRecord, TenantDB
from app.auth import get_current_tenant
from app.core import ReplenishmentCalculator, ReplenishmentInput

router = APIRouter()


# ============================================================
# Pydantic Schemas
# ============================================================

class CalculateRequest(BaseModel):
    sku_code: str
    current_stock: Optional[int] = None        # 不传则自动取最新
    in_transit_stock: Optional[int] = None    # 不传则自动取最新
    avg_daily_sales: Optional[float] = None    # 不传则自动计算


class BatchCalculateRequest(BaseModel):
    sku_codes: List[str]


class ShippingOption(BaseModel):
    name: str
    days: int
    cost_per_unit: float
    total_cost: float
    arrive_before_stockout: bool
    recommended: bool
    extra_cost: Optional[float] = None
    savings_vs_stockout: Optional[float] = None


class ReplenishmentResult(BaseModel):
    sku_id: str
    recommended_quantity: int
    mode: str
    urgency_level: str
    current_stock: int
    in_transit_stock: int
    days_cover: float
    days_cover_after_transit: float
    latest_order_date: str
    estimated_arrival_date: str
    estimated_cost: float
    estimated_profit: float
    risk_score: int
    risk_level: str
    priority_rank: int
    recommendations: List[str]
    shipping_options: dict


class BatchCalculateResponse(BaseModel):
    results: List[ReplenishmentResult]
    total_count: int
    high_risk_count: int


# ============================================================
# 工具函数
# ============================================================

def fetch_sku_data(session, sku_code: str):
    """从数据库获取SKU和最新库存/销量数据"""
    sku = session.query(SKU).filter_by(sku_code=sku_code, is_active=True).first()
    if not sku:
        raise HTTPException(status_code=404, detail=f"SKU {sku_code} 不存在")

    # 最新库存
    latest_inv = session.query(Inventory).filter_by(sku_id=sku.id).order_by(
        Inventory.record_date.desc()
    ).first()

    # 最近30天销量
    from datetime import timedelta
    thirty_days_ago = datetime.now() - timedelta(days=30)
    sales_records = session.query(SalesRecord).filter(
        SalesRecord.sku_id == sku.id,
        SalesRecord.sale_date >= thirty_days_ago,
    ).all()

    avg_sales = 0.0
    sales_history = []
    if sales_records:
        avg_sales = sum(r.quantity_sold for r in sales_records) / len(sales_records)
        sales_history = [(r.sale_date, r.quantity_sold) for r in sales_records]

    return sku, latest_inv, avg_sales, sales_records, sales_history


# ============================================================
# 路由
# ============================================================

@router.post("/calculate", response_model=ReplenishmentResult)
def calculate_replenishment(data: CalculateRequest, tenant_id: str = Depends(get_current_tenant)):
    """计算单个SKU的补货建议"""
    session = TenantDB.get_session(tenant_id)
    try:
        sku, latest_inv, avg_sales, _, sales_history = fetch_sku_data(session, data.sku_code)

        # 使用请求参数或自动获取
        current_stock = data.current_stock if data.current_stock is not None else (
            latest_inv.current_stock if latest_inv else 0
        )
        in_transit = data.in_transit_stock if data.in_transit_stock is not None else (
            latest_inv.in_transit_stock if latest_inv else 0
        )
        avg_daily_sales = data.avg_daily_sales if data.avg_daily_sales is not None else avg_sales

        # 构建输入
        inp = ReplenishmentInput(
            sku_id=sku.sku_code,
            current_stock=current_stock,
            in_transit_stock=in_transit,
            lead_time_days=sku.lead_time_days,
            avg_daily_sales=avg_daily_sales,
            sales_history=sales_history,
            safety_factor=sku.safety_factor,
            min_stock_days=sku.min_stock_days,
            supply_stability=sku.supply_stability,
            product_cost_per_unit=sku.product_cost,
            freight_cost_per_unit=sku.freight_cost,
            selling_price=sku.selling_price,
            fba_fee_per_unit=sku.fba_fee,
        )

        # 计算
        calc = ReplenishmentCalculator()
        result = calc.calculate(inp)

        return ReplenishmentResult(
            sku_id=result.sku_id,
            recommended_quantity=result.recommended_quantity,
            mode=result.mode,
            urgency_level=result.urgency_level,
            current_stock=result.current_stock,
            in_transit_stock=result.in_transit_stock,
            days_cover=result.days_cover,
            days_cover_after_transit=result.days_cover_after_transit,
            latest_order_date=result.latest_order_date,
            estimated_arrival_date=result.estimated_arrival_date,
            estimated_cost=result.estimated_cost,
            estimated_profit=result.estimated_profit,
            risk_score=result.risk_score,
            risk_level=result.risk_level,
            priority_rank=result.priority_rank,
            recommendations=result.recommendations,
            shipping_options=result.shipping_options,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/batch", response_model=BatchCalculateResponse)
def batch_calculate(data: BatchCalculateRequest, tenant_id: str = Depends(get_current_tenant)):
    """批量计算多个SKU的补货建议"""
    session = TenantDB.get_session(tenant_id)
    try:
        results = []
        high_risk_count = 0

        for sku_code in data.sku_codes:
            try:
                sku, latest_inv, avg_sales, _, sales_history = fetch_sku_data(session, sku_code)

                inp = ReplenishmentInput(
                    sku_id=sku.sku_code,
                    current_stock=latest_inv.current_stock if latest_inv else 0,
                    in_transit_stock=latest_inv.in_transit_stock if latest_inv else 0,
                    lead_time_days=sku.lead_time_days,
                    avg_daily_sales=avg_sales,
                    sales_history=sales_history,
                    safety_factor=sku.safety_factor,
                    min_stock_days=sku.min_stock_days,
                    supply_stability=sku.supply_stability,
                    product_cost_per_unit=sku.product_cost,
                    freight_cost_per_unit=sku.freight_cost,
                    selling_price=sku.selling_price,
                    fba_fee_per_unit=sku.fba_fee,
                )

                calc = ReplenishmentCalculator()
                result = calc.calculate(inp)
                results.append(ReplenishmentResult(
                    sku_id=result.sku_id,
                    recommended_quantity=result.recommended_quantity,
                    mode=result.mode,
                    urgency_level=result.urgency_level,
                    current_stock=result.current_stock,
                    in_transit_stock=result.in_transit_stock,
                    days_cover=result.days_cover,
                    days_cover_after_transit=result.days_cover_after_transit,
                    latest_order_date=result.latest_order_date,
                    estimated_arrival_date=result.estimated_arrival_date,
                    estimated_cost=result.estimated_cost,
                    estimated_profit=result.estimated_profit,
                    risk_score=result.risk_score,
                    risk_level=result.risk_level,
                    priority_rank=result.priority_rank,
                    recommendations=result.recommendations,
                    shipping_options=result.shipping_options,
                ))

                if result.risk_level == "high":
                    high_risk_count += 1

            except HTTPException:
                continue  # 跳过不存在的SKU

        # 批量排序
        if results:
            results.sort(key=lambda x: (100 - x.risk_score, x.days_cover))
            for i, r in enumerate(results):
                r.priority_rank = i + 1

        return BatchCalculateResponse(
            results=results,
            total_count=len(results),
            high_risk_count=high_risk_count,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{sku_code}", response_model=List[dict])
def get_replenishment_history(sku_code: str, limit: int = 10,
                               tenant_id: str = Depends(get_current_tenant)):
    """获取SKU的补货历史记录"""
    session = TenantDB.get_session(tenant_id)
    try:
        sku = session.query(SKU).filter_by(sku_code=sku_code, is_active=True).first()
        if not sku:
            raise HTTPException(status_code=404, detail=f"SKU {sku_code} 不存在")

        from app.models.database import Replenishment as ReplenishmentModel

        records = session.query(ReplenishmentModel).filter_by(sku_id=sku.id).order_by(
            ReplenishmentModel.order_date.desc()
        ).limit(limit).all()

        return [
            {
                "id": r.id,
                "order_date": r.order_date.isoformat() if r.order_date else None,
                "expected_arrival_date": r.expected_arrival_date.isoformat() if r.expected_arrival_date else None,
                "quantity_ordered": r.quantity_ordered,
                "quantity_received": r.quantity_received,
                "total_cost": r.total_cost,
                "mode": r.mode,
                "status": r.status,
                "risk_score": r.risk_score,
            }
            for r in records
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()