"""
安全系数计算器
根据销量波动性、季节性、供应链稳定性计算安全系数
"""

from typing import Optional
import math


class SafetyCalculator:
    """安全系数计算器"""

    # 默认安全系数
    DEFAULT_SAFETY_FACTOR = 1.15

    # 供应链稳定性评分 -> 系数乘数
    SUPPLY_STABILITY_MAP = {
        "stable": 1.0,       # 稳定供应，可降低安全系数
        "normal": 1.1,      # 正常
        "unstable": 1.25,  # 供应不稳定，提高安全系数
        "new_supplier": 1.4,  # 新供应商，最高安全系数
    }

    def __init__(self):
        self.lead_time_variability: float = 0.0  # 交期波动系数
        self.demand_volatility: float = 0.0       # 需求波动系数

    def calculate(
        self,
        lead_time_days: int,
        avg_lead_time_days: float,
        lead_time_std: Optional[float] = None,
        demand_cv: Optional[float] = None,  # 需求变异系数 (std/mean)
        supply_stability: str = "normal",
    ) -> float:
        """
        计算综合安全系数

        公式：SF = (1 + 交期波动系数) × (1 + 需求波动系数) × 供应链系数

        Args:
            lead_time_days: 当前备货天数
            avg_lead_time_days: 平均备货天数
            lead_time_std: 备货天数标准差（可选）
            demand_cv: 需求变异系数（可选）
            supply_stability: 供应链稳定性

        Returns:
            float: 安全系数，通常 1.0 - 1.5
        """
        # 交期波动系数：实际备货天数偏离平均的程度
        if lead_time_std and avg_lead_time_days > 0:
            lt_cv = lead_time_std / avg_lead_time_days
        else:
            lt_cv = abs(lead_time_days - avg_lead_time_days) / max(avg_lead_time_days, 1) * 0.5

        demand_factor = demand_cv if demand_cv else self._estimate_demand_cv()
        supply_factor = self.SUPPLY_STABILITY_MAP.get(supply_stability, 1.1)

        safety_factor = (1 + lt_cv) * (1 + demand_factor) * supply_factor

        # 限制范围
        return max(1.0, min(1.5, round(safety_factor, 2)))

    def _estimate_demand_cv(self) -> float:
        """
        根据经验估算需求变异系数
        宠物滤芯类目：需求相对稳定，CV约 0.2-0.3
        """
        return 0.25  # 默认25%波动

    def calculate_z_score(
        self,
        current_stock: int,
        avg_daily_sales: float,
        lead_time_days: int,
        safety_factor: float,
    ) -> float:
        """
        计算安全库存Z分数

        Z = 当前库存 - (平均日销 × 备货天数 × 安全系数)

        Args:
            current_stock: 当前库存
            avg_daily_sales: 平均日销
            lead_time_days: 备货天数
            safety_factor: 安全系数

        Returns:
            float: Z分数，>0表示库存充足，<0表示可能断货
        """
        required_stock = avg_daily_sales * lead_time_days * safety_factor
        return (current_stock - required_stock) / max(avg_daily_sales, 1)

    def get_minimum_safety_stock(
        self,
        avg_daily_sales: float,
        lead_time_days: int,
        safety_factor: float = 1.15,
    ) -> int:
        """
        计算最低安全库存量

        公式：Z_min = D × T × S

        Args:
            avg_daily_sales: 平均日销
            lead_time_days: 备货天数
            safety_factor: 安全系数

        Returns:
            int: 最低安全库存数量
        """
        return int(math.ceil(avg_daily_sales * lead_time_days * safety_factor))