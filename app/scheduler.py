"""
定时任务调度器
功能：
1. 每日凌晨自动重算所有SKU的补货建议
2. 高风险SKU自动推送飞书通知
3. 补货记录自动归档

运行方式：
- 直接运行：python -m app.scheduler（后台常驻）
- 或部署到 cron：0 2 * * * cd /path && python -m app.scheduler
"""

import time
import logging
from datetime import datetime, timedelta
from threading import Thread

from app.models.database import SKU, Inventory, get_session
from app.core import ReplenishmentCalculator, ReplenishmentInput

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# 飞书通知
# ============================================================
import os

FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")


def send_feishu_alert(sku_code: str, product_name: str, risk_score: int,
                      days_cover: float, recommended_qty: int):
    """发送飞书高风险SKU告警"""
    if not FEISHU_WEBHOOK:
        logger.info(f"[跳过通知] 未配置FEISHU_WEBHOOK，SKU={sku_code}")
        return False
    try:
        import requests as _requests

        risk_emoji = "🔴" if risk_score >= 70 else "🟡"
        message = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": f"{risk_emoji} 高风险SKU告警",
                    "template": "red" if risk_score >= 70 else "orange",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**SKU：** {sku_code}\n**产品：** {product_name}\n"
                                     f"**风险评分：** {risk_score} 分\n**可售天数：** {days_cover:.1f} 天\n"
                                     f"**建议补货：** {recommended_qty:,} 个",
                        }
                    },
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"🕐 触发时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        }
                    },
                ]
            }
        }

        r = _requests.post(FEISHU_WEBHOOK, json=message, timeout=10)
        logger.info(f"飞书通知已发送：{sku_code} (status={r.status_code})")
        return r.status_code == 200
    except Exception as e:
        logger.warning(f"飞书通知发送失败：{e}")
        return False


# ============================================================
# 每日重算核心逻辑
# ============================================================

def recalculate_all_skus():
    """重新计算所有活跃SKU的补货建议，返回高风险列表"""
    logger.info("开始每日补货重算...")
    session = get_session()
    high_risk_skus = []

    try:
        skus = session.query(SKU).filter_by(is_active=True).all()

        for sku in skus:
            try:
                # 获取最新库存
                latest_inv = session.query(Inventory).filter_by(
                    sku_id=sku.id
                ).order_by(Inventory.record_date.desc()).first()

                if not latest_inv:
                    continue

                # 获取30天销量
                thirty_days_ago = datetime.now() - timedelta(days=30)
                from app.models.database import SalesRecord
                sales_records = session.query(SalesRecord).filter(
                    SalesRecord.sku_id == sku.id,
                    SalesRecord.sale_date >= thirty_days_ago,
                ).all()

                avg_sales = 0.0
                if sales_records:
                    avg_sales = sum(r.quantity_sold for r in sales_records) / len(sales_records)

                # 构建输入
                inp = ReplenishmentInput(
                    sku_id=sku.sku_code,
                    current_stock=latest_inv.current_stock,
                    in_transit_stock=latest_inv.in_transit_stock,
                    lead_time_days=sku.lead_time_days,
                    avg_daily_sales=avg_sales,
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

                if result.risk_level == "high":
                    high_risk_skus.append({
                        "sku_code": sku.sku_code,
                        "product_name": sku.product_name,
                        "risk_score": result.risk_score,
                        "days_cover": result.days_cover,
                        "recommended_qty": result.recommended_quantity,
                    })

            except Exception as e:
                logger.warning(f"SKU {sku.sku_code} 重算失败：{e}")
                continue

        logger.info(f"重算完成，高风险SKU：{len(high_risk_skus)} 个")

        # 发送飞书通知
        for item in high_risk_skus:
            send_feishu_alert(
                item["sku_code"], item["product_name"],
                item["risk_score"], item["days_cover"], item["recommended_qty"],
            )

        return high_risk_skus

    finally:
        session.close()


# ============================================================
# 调度器主循环（可选常驻模式）
# ============================================================

class ReplenishmentScheduler:
    """补货调度器"""

    def __init__(self, check_interval_hours: int = 24):
        self.check_interval = check_interval_hours * 3600
        self._running = False

    def start(self):
        """启动调度器（后台线程）"""
        self._running = True
        thread = Thread(target=self._loop, daemon=True)
        thread.start()
        logger.info("调度器已启动")

    def stop(self):
        """停止调度器"""
        self._running = False

    def _loop(self):
        """主循环"""
        while self._running:
            try:
                recalculate_all_skus()
            except Exception as e:
                logger.error(f"调度任务异常：{e}")

            # 分段睡眠，支持快速停止
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)


# ============================================================
# 入口
# ============================================================

def main():
    print("=" * 50)
    print("智能补货引擎 - 定时任务调度器")
    print("=" * 50)
    print(f"运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 单次运行模式（推荐用于 cron）
    high_risk = recalculate_all_skus()

    print()
    print("=" * 50)
    print(f"✅ 执行完成。高风险SKU：{len(high_risk)} 个")
    for item in high_risk:
        print(f"  {item['sku_code']} | {item['product_name']} | "
              f"风险{item['risk_score']}分 | 可售{item['days_cover']:.1f}天")
    print("=" * 50)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        # 常驻模式
        scheduler = ReplenishmentScheduler(check_interval_hours=24)
        scheduler.start()
        print("调度器常驻运行中，按 Ctrl+C 停止")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            scheduler.stop()
            print("调度器已停止")
    else:
        # 单次模式
        main()