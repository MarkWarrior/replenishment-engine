"""
销量预测模型
支持：简单移动平均、加权移动平均、指数平滑、季节性调整
"""

from typing import List, Optional, Dict
from datetime import datetime, timedelta
import math


class SalesPredictor:
    """销量预测器"""

    def __init__(self):
        self.sales_history: List[float] = []
        self.dates: List[datetime] = []

    def add_sales_data(self, date: datetime, quantity: float):
        """添加历史销量数据"""
        self.dates.append(date)
        self.sales_history.append(quantity)

    def simple_moving_average(self, window: int = 30) -> float:
        """
        简单移动平均 (SMA)

        公式：SMA = Σ(销量) / N

        Args:
            window: 窗口大小，默认30天

        Returns:
            float: 日均销量预测
        """
        if not self.sales_history:
            return 0.0

        data = self.sales_history[-window:]
        return sum(data) / len(data)

    def weighted_moving_average(
        self,
        window: int = 30,
        recent_weight: float = 3.0,
        mid_weight: float = 2.0,
        old_weight: float = 1.0,
    ) -> float:
        """
        加权移动平均 (WMA)

        公式：WMA = (7天×3 + 14天×2 + 30天×1) / (7×3 + 14×2 + 30×1)

        Args:
            window: 窗口大小
            recent_weight: 近端权重
            mid_weight: 中间权重
            old_weight: 远端权重

        Returns:
            float: 日均销量预测
        """
        if len(self.sales_history) < 7:
            return self.simple_moving_average(window)

        data = self.sales_history[-window:]

        # 分段计算权重
        recent = data[-7:] if len(data) >= 7 else data
        mid = data[-14:-7] if len(data) >= 14 else data[:-7] if len(data) > 7 else []
        old = data[:-14] if len(data) >= 14 else []

        # 带权重的均值
        total_weight = len(recent) * recent_weight + len(mid) * mid_weight + len(old) * old_weight
        if total_weight == 0:
            return 0.0

        weighted_sum = (
            sum(recent) * recent_weight
            + sum(mid) * mid_weight
            + sum(old) * old_weight
        )

        return weighted_sum / total_weight

    def exponential_moving_average(self, alpha: float = 0.3) -> float:
        """
        指数平滑 (EMA)

        公式：EMA_t = α × 销量_t + (1-α) × EMA_{t-1}

        Args:
            alpha: 平滑系数，0-1之间，越大越重视近期数据

        Returns:
            float: 日均销量预测
        """
        if not self.sales_history:
            return 0.0

        ema = self.sales_history[0]
        for sale in self.sales_history[1:]:
            ema = alpha * sale + (1 - alpha) * ema

        return ema

    def predict_with_trend(
        self,
        window: int = 30,
    ) -> Dict[str, float]:
        """
        带趋势的销量预测

        分析最近销量的趋势（上浮/下跌），并调整预测值

        Returns:
            Dict包含:
                - predicted: 预测日均销量
                - trend: 趋势系数（>1上涨，<1下跌）
                - trend_direction: 趋势方向
        """
        if len(self.sales_history) < 14:
            return {
                "predicted": self.weighted_moving_average(window),
                "trend": 1.0,
                "trend_direction": "stable",
            }

        # 最近14天 vs 前14天
        recent_14 = self.sales_history[-14:]
        previous_14 = self.sales_history[-28:-14] if len(self.sales_history) >= 28 else self.sales_history[:-14]
        previous_14 = previous_14[-14:] if len(previous_14) > 14 else previous_14

        if not previous_14:
            return {
                "predicted": self.weighted_moving_average(window),
                "trend": 1.0,
                "trend_direction": "stable",
            }

        avg_recent = sum(recent_14) / len(recent_14)
        avg_previous = sum(previous_14) / len(previous_14)

        if avg_previous == 0:
            trend = 1.0
        else:
            trend = avg_recent / avg_previous

        base_prediction = self.weighted_moving_average(window)
        predicted = base_prediction * trend

        # 趋势方向判断
        if trend > 1.1:
            direction = "increasing"
        elif trend < 0.9:
            direction = "decreasing"
        else:
            direction = "stable"

        return {
            "predicted": max(0, predicted),
            "trend": round(trend, 3),
            "trend_direction": direction,
        }

    def detect_seasonality(self, data: Optional[List[float]] = None) -> Optional[float]:
        """
        检测季节性因子

        当前周 vs 上周的平均值比例

        Args:
            data: 可选，指定数据，默认使用最近7天

        Returns:
            float: 季节性因子，>1表示旺季，<1表示淡季
        """
        if data is None:
            data = self.sales_history

        if len(data) < 14:
            return None

        last_week = data[-7:]
        prev_week = data[-14:-7]

        avg_last = sum(last_week) / len(last_week)
        avg_prev = sum(prev_week) / len(prev_week)

        if avg_prev == 0:
            return None

        return avg_last / avg_prev

    def predict(
        self,
        method: str = "weighted",
        window: int = 30,
    ) -> float:
        """
        综合预测入口

        Args:
            method: 预测方法
                - "simple": 简单移动平均
                - "weighted": 加权移动平均
                - "ema": 指数平滑
                - "trend": 带趋势预测
            window: 窗口大小

        Returns:
            float: 预测日均销量
        """
        method = method.lower()

        if method == "simple":
            return self.simple_moving_average(window)
        elif method == "weighted":
            return self.weighted_moving_average(window)
        elif method == "ema":
            return self.exponential_moving_average()
        elif method == "trend":
            return self.predict_with_trend(window)["predicted"]
        else:
            return self.weighted_moving_average(window)

    def get_sales_volatility(self, window: int = 30) -> float:
        """
        计算销量波动性（标准差/均值）

        用于安全系数计算
        """
        if len(self.sales_history) < 2:
            return 0.0

        data = self.sales_history[-window:]
        mean = sum(data) / len(data)

        if mean == 0:
            return 0.0

        variance = sum((x - mean) ** 2 for x in data) / len(data)
        std = math.sqrt(variance)

        return std / mean  # CV (变异系数)