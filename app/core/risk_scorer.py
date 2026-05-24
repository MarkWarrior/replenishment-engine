"""
断货风险评分器
综合库存、销量、竞品等因素计算断货风险分数（0-100）
"""

from typing import Optional, Dict
from datetime import datetime


class RiskScorer:
    """断货风险评分器"""

    # 风险等级阈值（调整后更符合实际业务感知）
    # 高风险：综合断货风险 >= 70（3天库存约78分，7天库存约56分）
    # 中风险：综合断货风险 >= 45（14天库存约48分）
    RISK_HIGH = 70
    RISK_MEDIUM = 45
    RISK_LOW = 25

    def __init__(self):
        # 权重分布（总分100）
        # days_cover权重最高，因为这是最直接的断货指标
        self.weights = {
            "days_cover": 30,         # 库存可售天数
            "sales_volatility": 20,   # 销量波动
            "price_pressure": 15,     # 价格压力
            "seasonality": 15,       # 季节性
            "competitor_status": 10, # 竞品状态
            "reviews": 10,            # 差评影响
        }

    def calculate_risk_score(
        self,
        days_cover: float,
        sales_volatility: float = 0.1,
        competitor_price_trend: str = "stable",
        is_peak_season: bool = False,
        recent_neg_reviews: int = 0,
    ) -> Dict[str, any]:
        """
        计算综合断货风险分数

        Args:
            days_cover: 库存可售天数
            sales_volatility: 销量波动（CV值，0-1之间）
            competitor_price_trend: 竞品价格趋势 ("rising"|"stable"|"falling")
            is_peak_season: 是否旺季
            recent_neg_reviews: 近期差评数

        Returns:
            Dict包含:
                - score: 风险分数（0-100）
                - level: 风险等级（high/medium/low）
                - factors: 各因子得分详情
                - urgency: 紧急程度描述
                - recommendations: 建议措施
        """
        # 因子1：库存可售天数得分（0-30分）- 权重最高
        cover_score = self._score_days_cover(days_cover)

        # 因子2：销量波动得分（0-20分）
        volatility_score = self._score_volatility(sales_volatility)

        # 因子3：价格压力得分（0-15分）
        price_score = self._score_price_pressure(competitor_price_trend)

        # 因子4：季节性因子得分（0-15分）
        season_score = self._score_seasonality(is_peak_season)

        # 因子5：竞品状态（0-10分）
        competitor_score = self._score_competitor(competitor_price_trend)

        # 因子6：差评影响得分（0-10分）
        review_score = self._score_reviews(recent_neg_reviews)

        total_score = cover_score + volatility_score + price_score + season_score + competitor_score + review_score

        # 风险等级
        if total_score >= self.RISK_HIGH:
            level = "high"
        elif total_score >= self.RISK_MEDIUM:
            level = "medium"
        else:
            level = "low"

        # 紧急程度描述
        urgency = self._get_urgency_description(days_cover, total_score)

        # 建议措施
        recommendations = self._get_recommendations(level, days_cover)

        return {
            "score": min(100, total_score),
            "level": level,
            "factors": {
                "days_cover_score": cover_score,
                "volatility_score": volatility_score,
                "price_score": price_score,
                "season_score": season_score,
                "competitor_score": competitor_score,
                "review_score": review_score,
            },
            "urgency": urgency,
            "recommendations": recommendations,
        }

    def _score_days_cover(self, days: float) -> float:
        """
        库存可售天数得分（0-55分）- 核心指标，占总分一半以上

        评分标准（指数衰减，越少分越高）：
        - <=3天：55分（极危险，接近断货）
        - <=5天：45分
        - <=7天：38分（紧急补货线）
        - <=10天：28分
        - <=14天：25分
        - <=21天：12分
        - <=30天：5分
        - >30天：0分
        """
        if days <= 3:
            return 55.0
        elif days <= 5:
            return 45.0
        elif days <= 7:
            return 38.0
        elif days <= 10:
            return 28.0
        elif days <= 14:
            return 25.0
        elif days <= 21:
            return 12.0
        elif days <= 30:
            return 5.0
        else:
            return 0.0

    def _score_volatility(self, cv: float) -> float:
        """
        销量波动得分（0-20分）
        波动越大，分数越高

        评分标准（基于变异系数CV）：
        - CV <= 0.1：0分（稳定）
        - CV 0.1-0.2：5分
        - CV 0.2-0.3：10分
        - CV 0.3-0.5：15分
        - CV > 0.5：20分（高波动）
        """
        if cv <= 0.1:
            return 0.0
        elif cv <= 0.2:
            return 5.0
        elif cv <= 0.3:
            return 10.0
        elif cv <= 0.5:
            return 15.0
        else:
            return 20.0

    def _score_price_pressure(self, trend: str) -> float:
        """
        价格压力得分（0-15分）
        竞品涨价→风险降低；竞品降价→风险升高

        评分标准：
        - rising（竞品涨价）：0分（对我们有利）
        - stable：8分
        - falling（竞品降价）：15分（价格战风险）
        """
        if trend == "rising":
            return 0.0
        elif trend == "falling":
            return 15.0
        else:
            return 8.0

    def _score_seasonality(self, is_peak: bool) -> float:
        """
        季节性得分（0-15分）
        旺季需求大，断货风险高
        """
        if is_peak:
            return 15.0
        else:
            return 5.0

    def _score_competitor(self, trend: str) -> float:
        """
        竞品状态得分（0-10分）
        竞品断货时，我们需求可能上涨
        """
        if trend == "rising":
            return 10.0  # 竞品在涨价，可能快断货了
        elif trend == "falling":
            return 3.0
        else:
            return 5.0

    def _score_reviews(self, neg_count: int) -> float:
        """
        差评影响得分（0-10分）
        差评多可能影响销量，进而影响补货节奏
        """
        if neg_count == 0:
            return 0.0
        elif neg_count <= 2:
            return 3.0
        elif neg_count <= 5:
            return 6.0
        else:
            return 10.0

    def _get_urgency_description(self, days: float, score: float) -> str:
        """根据可售天数和总分返回紧急程度描述"""
        if days <= 3 or score >= 80:
            return "🚨 紧急：立即补货，空运优先"
        elif days <= 7 or score >= 50:
            return "⚠️ 警告：7天内必须补货，海运来得及"
        elif days <= 14 or score >= 30:
            return "🔔 关注：2周内安排补货"
        else:
            return "✅ 正常：库存充足，可按计划补货"

    def _get_recommendations(self, level: str, days: float) -> list:
        """根据风险等级返回建议措施"""
        if level == "high":
            return [
                "立即下单，空运优先",
                "联系供应商加急生产",
                f"当前库存仅够{days:.0f}天，必须快速补货",
                "考虑分批发货：先空运一部分保排名，海运跟进",
            ]
        elif level == "medium":
            return [
                "本周内完成补货",
                "优先选择海运节省成本",
                f"当前库存可售{days:.0f}天",
                "持续监控销量变化",
            ]
        else:
            return [
                "按正常节奏补货即可",
                "保持当前备货天数在14天以上",
                "每月固定补货日，养成规律",
            ]

    def get_risk_color(self, level: str) -> str:
        """返回风险等级对应的颜色"""
        colors = {
            "high": "#FF4444",
            "medium": "#FFA500",
            "low": "#44BB44",
        }
        return colors.get(level, "#888888")

    def get_risk_emoji(self, level: str) -> str:
        """返回风险等级对应的emoji"""
        emojis = {
            "high": "🔴",
            "medium": "🟡",
            "low": "🟢",
        }
        return emojis.get(level, "⚪")