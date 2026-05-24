"""
智能补货计算引擎
支持三种补货模式：紧急补货、标准补货、优化补货
"""

from typing import Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math

from .predictor import SalesPredictor
from .safety import SafetyCalculator
from .risk_scorer import RiskScorer


@dataclass
class ReplenishmentInput:
    """补货计算输入参数"""
    sku_id: str
    current_stock: int           # 当前在库库存
    in_transit_stock: int = 0    # 在途库存（已下单未到仓）
    lead_time_days: int = 30      # 备货天数（生产+头程+入仓）
    avg_daily_sales: float = 0.0  # 平均日均销量
    sales_history: List[tuple] = field(default_factory=list)  # [(date, quantity), ...]
    safety_factor: float = 1.15   # 安全系数
    min_stock_days: int = 7      # 最低库存可售天数（低于此值触发补货）
    supply_stability: str = "normal"  # 供应链稳定性
    freight_cost_per_unit: float = 0.0  # 单个运费成本
    product_cost_per_unit: float = 0.0  # 单个产品成本
    selling_price: float = 0.0    # 售价（用于利润计算）
    fba_fee_per_unit: float = 0.0  # FBA费用/个


@dataclass
class ReplenishmentOutput:
    """补货计算输出结果"""
    sku_id: str
    recommended_quantity: int     # 建议补货数量
    mode: str                     # 补货模式：urgent/standard/optimized
    urgency_level: str            # 紧急程度：high/medium/low

    # 库存状态
    current_stock: int
    in_transit_stock: int
    days_cover: float             # 可售天数
    days_cover_after_transit: float  # 在途到货后可售天数

    # 时间
    latest_order_date: str        # 最迟下单日期
    estimated_arrival_date: str   # 预计到仓日期

    # 成本
    estimated_cost: float         # 预计补货总成本
    estimated_profit: float       # 预计补货后利润增量

    # 风险
    risk_score: int               # 断货风险分数（0-100）
    risk_level: str               # 风险等级

    # 优先级
    priority_rank: int            # 补货优先级排名

    # 推荐方案
    recommendations: List[str]    # 行动建议
    shipping_options: Dict[str, dict] = field(default_factory=dict)  # 各运输方案对比


class ReplenishmentCalculator:
    """智能补货计算引擎"""

    # 补货模式阈值
    URGENT_DAYS = 7    # <=7天 触发紧急补货
    STANDARD_DAYS = 21 # <=21天 触发标准补货
    # >21天 触发优化补货

    # 空运 vs 海运时效差异
    AIR_FREIGHT_DAYS = 10
    SEA_FREIGHT_DAYS = 30

    def __init__(self):
        self.safety_calc = SafetyCalculator()
        self.risk_scorer = RiskScorer()
        self.predictor = SalesPredictor()

    def calculate(self, input_data: ReplenishmentInput) -> ReplenishmentOutput:
        """
        主入口：计算补货建议

        Args:
            input_data: 补货输入参数

        Returns:
            ReplenishmentOutput: 补货建议输出
        """
        # 1. 计算日均销量（如有历史数据则预测，否则用给定值）
        if input_data.sales_history:
            for date, qty in input_data.sales_history:
                self.predictor.add_sales_data(date, qty)
            avg_daily_sales = self.predictor.weighted_moving_average()
        else:
            avg_daily_sales = input_data.avg_daily_sales

        if avg_daily_sales <= 0:
            avg_daily_sales = 1.0  # 防止除零

        # 2. 计算安全系数
        safety_factor = self.safety_calc.calculate(
            lead_time_days=input_data.lead_time_days,
            avg_lead_time_days=input_data.lead_time_days,
            supply_stability=input_data.supply_stability,
        )

        # 3. 计算可售天数
        days_cover = input_data.current_stock / avg_daily_sales
        transit_days = input_data.lead_time_days if input_data.in_transit_stock > 0 else 0
        days_cover_after_transit = (input_data.current_stock + input_data.in_transit_stock) / avg_daily_sales

        # 4. 确定补货模式
        mode = self._determine_mode(days_cover)

        # 5. 计算建议补货数量
        recommended_qty = self._calculate_quantity(
            input_data=input_data,
            avg_daily_sales=avg_daily_sales,
            safety_factor=safety_factor,
            days_cover=days_cover,
        )

        # 6. 计算时间节点
        latest_order = datetime.now() + timedelta(days=max(0, days_cover - input_data.lead_time_days))
        estimated_arrival = datetime.now() + timedelta(days=input_data.lead_time_days)

        # 7. 计算断货风险
        risk_result = self.risk_scorer.calculate_risk_score(
            days_cover=days_cover,
            sales_volatility=self.predictor.get_sales_volatility() if input_data.sales_history else 0.1,
        )

        # 8. 计算成本和利润
        total_cost = self._calculate_replenishment_cost(input_data, recommended_qty)
        estimated_profit = self._calculate_profit_increment(input_data, recommended_qty, avg_daily_sales)

        # 9. 生成运输方案对比
        shipping_options = self._generate_shipping_options(
            input_data=input_data,
            recommended_qty=recommended_qty,
            days_cover=days_cover,
        )

        # 10. 生成行动建议
        recommendations = self._generate_recommendations(
            mode=mode,
            days_cover=days_cover,
            risk_level=risk_result["level"],
            recommended_qty=recommended_qty,
            avg_daily_sales=avg_daily_sales,
        )

        return ReplenishmentOutput(
            sku_id=input_data.sku_id,
            recommended_quantity=recommended_qty,
            mode=mode,
            urgency_level=risk_result["level"],
            current_stock=input_data.current_stock,
            in_transit_stock=input_data.in_transit_stock,
            days_cover=round(days_cover, 1),
            days_cover_after_transit=round(days_cover_after_transit, 1),
            latest_order_date=latest_order.strftime("%Y-%m-%d"),
            estimated_arrival_date=estimated_arrival.strftime("%Y-%m-%d"),
            estimated_cost=round(total_cost, 2),
            estimated_profit=round(estimated_profit, 2),
            risk_score=int(risk_result["score"]),
            risk_level=risk_result["level"],
            priority_rank=0,  # 后续由调用方排序
            recommendations=recommendations,
            shipping_options=shipping_options,
        )

    def _determine_mode(self, days_cover: float) -> str:
        """确定补货模式"""
        if days_cover <= self.URGENT_DAYS:
            return "urgent"
        elif days_cover <= self.STANDARD_DAYS:
            return "standard"
        else:
            return "optimized"

    def _calculate_quantity(
        self,
        input_data: ReplenishmentInput,
        avg_daily_sales: float,
        safety_factor: float,
        days_cover: float,
    ) -> int:
        """
        计算建议补货数量

        核心公式：Q = max(安全库存, 目标库存) - 当前库存 - 在途库存

        安全库存 = 日均销量 × 备货天数 × 安全系数

        根据模式调整：
        - urgent: 覆盖30天空运
        - standard: 覆盖T+7天
        - optimized: 利润最优
        """
        # 基础安全库存
        base_stock = avg_daily_sales * input_data.lead_time_days * safety_factor

        if days_cover <= self.URGENT_DAYS:
            # 紧急模式：覆盖30天空运 + 安全库存
            target_stock = avg_daily_sales * (self.AIR_FREIGHT_DAYS + 7) * safety_factor
        elif days_cover <= self.STANDARD_DAYS:
            # 标准模式：覆盖备货天数 + 7天缓冲
            target_stock = avg_daily_sales * (input_data.lead_time_days + 7) * safety_factor
        else:
            # 优化模式：刚好覆盖备货天数
            target_stock = avg_daily_sales * input_data.lead_time_days * safety_factor

        # 目标库存 = max(安全库存, 目标库存)
        target_stock = max(base_stock, target_stock)

        # 补货数量 = 目标库存 - 当前库存 - 在途库存
        qty = target_stock - input_data.current_stock - input_data.in_transit_stock

        # 最少补货量（防止小批量补货）
        qty = max(qty, 0)  # 不允许负数（库存充足时）
        qty = max(qty, 50) if avg_daily_sales > 5 else max(qty, 20)  # 最低补货量

        return int(math.ceil(qty))

    def _calculate_replenishment_cost(
        self,
        input_data: ReplenishmentInput,
        quantity: int,
    ) -> float:
        """计算补货总成本"""
        if quantity <= 0:
            return 0.0

        cost = 0.0
        cost += input_data.product_cost_per_unit * quantity
        cost += input_data.freight_cost_per_unit * quantity
        cost += input_data.fba_fee_per_unit * quantity

        return cost

    def _calculate_profit_increment(
        self,
        input_data: ReplenishmentInput,
        quantity: int,
        avg_daily_sales: float,
    ) -> float:
        """计算补货后预期利润增量"""
        if quantity <= 0 or input_data.selling_price <= 0:
            return 0.0

        # 预计这批货可销售天数
        days_to_sell = quantity / avg_daily_sales if avg_daily_sales > 0 else 30

        # 单位利润
        referral_fee = input_data.selling_price * 0.15  # 15% referral fee
        unit_profit = input_data.selling_price - input_data.product_cost_per_unit - referral_fee

        # 简化：假设补货的quantity能在这个周期内全部卖出
        return unit_profit * quantity * 0.8  # 80%实现率

    def _generate_shipping_options(
        self,
        input_data: ReplenishmentInput,
        recommended_qty: int,
        days_cover: float,
    ) -> Dict[str, dict]:
        """生成运输方案对比"""
        options = {}

        if days_cover <= self.URGENT_DAYS:
            # 必须空运
            air_cost = recommended_qty * 2.5  # 空运单价估算（约海运3倍）
            options["air"] = {
                "name": "空运",
                "days": self.AIR_FREIGHT_DAYS,
                "cost_per_unit": 2.5,
                "total_cost": air_cost,
                "arrive_before_stockout": True,
                "recommended": True,
                "savings_vs_stockout": recommended_qty * input_data.selling_price * 0.3,
            }
        elif days_cover <= self.STANDARD_DAYS:
            # 海运优先，空运备选
            sea_cost = recommended_qty * 0.8  # 海运单价
            options["sea"] = {
                "name": "海运",
                "days": self.SEA_FREIGHT_DAYS,
                "cost_per_unit": 0.8,
                "total_cost": sea_cost,
                "arrive_before_stockout": days_cover >= 5,
                "recommended": True,
            }
            options["air"] = {
                "name": "空运",
                "days": self.AIR_FREIGHT_DAYS,
                "cost_per_unit": 2.5,
                "total_cost": recommended_qty * 2.5,
                "arrive_before_stockout": True,
                "recommended": False,
                "extra_cost": recommended_qty * 1.7,
            }
        else:
            # 优化模式，仅海运
            options["sea"] = {
                "name": "海运",
                "days": self.SEA_FREIGHT_DAYS,
                "cost_per_unit": 0.8,
                "total_cost": recommended_qty * 0.8,
                "arrive_before_stockout": True,
                "recommended": True,
            }

        return options

    def _generate_recommendations(
        self,
        mode: str,
        days_cover: float,
        risk_level: str,
        recommended_qty: int,
        avg_daily_sales: float,
    ) -> List[str]:
        """生成行动建议"""
        recs = []

        if mode == "urgent":
            recs.append(f"🚨 紧急补货：立即下单，空运优先")
            recs.append(f"建议数量：{recommended_qty}个（覆盖30天销售）")
            recs.append(f"当前库存仅够 {days_cover:.0f} 天，必须快速补货")
        elif mode == "standard":
            recs.append(f"⚠️ 标准补货：本周内完成下单，海运优先")
            recs.append(f"建议数量：{recommended_qty}个")
            recs.append(f"当前库存可售 {days_cover:.0f} 天，来得及海运")
        else:
            recs.append(f"✅ 优化补货：按计划补货即可")
            recs.append(f"建议数量：{recommended_qty}个")
            recs.append(f"当前库存充足，可按正常节奏补货")

        return recs

    def batch_calculate(self, inputs: List[ReplenishmentInput]) -> List[ReplenishmentOutput]:
        """
        批量计算多个SKU的补货建议

        按风险等级和紧迫程度排序
        """
        results = []
        for inp in inputs:
            result = self.calculate(inp)
            results.append(result)

        # 按风险分数和可售天数排序
        results.sort(key=lambda x: (100 - x.risk_score, x.days_cover))

        # 更新优先级
        for i, r in enumerate(results):
            r.priority_rank = i + 1

        return results