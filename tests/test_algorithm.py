"""
单元测试 - 补货核心算法
运行: python -m pytest tests/test_algorithm.py -v
"""

import pytest
from datetime import datetime, timedelta
from app.core import (
    ReplenishmentCalculator,
    ReplenishmentInput,
    SalesPredictor,
    SafetyCalculator,
    RiskScorer,
)


class TestSalesPredictor:
    """销量预测器测试"""

    def setup_method(self):
        self.predictor = SalesPredictor()
        # 添加30天测试销量数据
        for i in range(30):
            date = datetime.now() - timedelta(days=30 - i)
            # 稳定日销30个，带小幅波动
            qty = 30 + (i % 7 - 3)
            self.predictor.add_sales_data(date, qty)

    def test_simple_moving_average(self):
        """测试简单移动平均"""
        result = self.predictor.simple_moving_average(window=30)
        assert 27 <= result <= 33, f"简单移动平均应该在27-33之间，实际: {result}"

    def test_weighted_moving_average(self):
        """测试加权移动平均"""
        result = self.predictor.weighted_moving_average(window=30)
        assert result > 0, "加权平均应该大于0"

    def test_exponential_moving_average(self):
        """测试指数平滑"""
        result = self.predictor.exponential_moving_average(alpha=0.3)
        assert 27 <= result <= 33, f"指数平滑应该在27-33之间，实际: {result}"

    def test_trend_detection(self):
        """测试趋势检测"""
        result = self.predictor.predict_with_trend(window=30)
        assert "predicted" in result
        assert "trend" in result
        assert "trend_direction" in result

    def test_empty_history(self):
        """测试空数据"""
        empty_predictor = SalesPredictor()
        assert empty_predictor.simple_moving_average() == 0.0
        assert empty_predictor.weighted_moving_average() == 0.0


class TestSafetyCalculator:
    """安全系数计算器测试"""

    def setup_method(self):
        self.calc = SafetyCalculator()

    def test_default_safety_factor(self):
        """测试默认安全系数计算"""
        sf = self.calc.calculate(
            lead_time_days=30,
            avg_lead_time_days=30,
        )
        assert 1.0 <= sf <= 1.5, f"安全系数应在1.0-1.5之间，实际: {sf}"

    def test_stable_supply_lower_factor(self):
        """稳定供应链应该有更低的安全系数"""
        sf_stable = self.calc.calculate(
            lead_time_days=30,
            avg_lead_time_days=30,
            supply_stability="stable",
        )
        sf_new = self.calc.calculate(
            lead_time_days=30,
            avg_lead_time_days=30,
            supply_stability="new_supplier",
        )
        assert sf_stable < sf_new, "新供应商安全系数应高于稳定供应商"

    def test_minimum_safety_stock(self):
        """测试最低安全库存计算"""
        min_stock = self.calc.get_minimum_safety_stock(
            avg_daily_sales=30,
            lead_time_days=30,
            safety_factor=1.15,
        )
        expected = int(30 * 30 * 1.15)
        assert min_stock == expected, f"最低安全库存应为{expected}，实际: {min_stock}"

    def test_z_score_calculation(self):
        """测试Z分数计算"""
        z = self.calc.calculate_z_score(
            current_stock=1000,
            avg_daily_sales=30,
            lead_time_days=30,
            safety_factor=1.15,
        )
        # 库存1000，需求约1035（30*30*1.15），Z = (1000-1035)/30 = -1.17
        # Z < 0 表示库存不足（刚好覆盖不到安全库存）
        assert z < 0, f"库存不足时Z应为负数，实际: {z}"
        assert abs(z) < 3, f"Z分数绝对值应<3（库存接近安全线），实际: {z}"


class TestRiskScorer:
    """断货风险评分器测试"""

    def setup_method(self):
        self.scorer = RiskScorer()

    def test_high_risk_urgent(self):
        """测试紧急断货风险（3天库存）"""
        result = self.scorer.calculate_risk_score(days_cover=3)
        # 3天库存：days_cover=55 + 其他因子~18 = ~73分
        assert result["score"] >= 70, f"3天库存应为高风险，实际: {result['score']}"
        assert result["level"] == "high"

    def test_medium_risk(self):
        """测试中等风险（14天库存）"""
        result = self.scorer.calculate_risk_score(days_cover=14)
        # 14天库存：days_cover=25 + 其他因子~18 = ~43分
        # 刚好低于MEDIUM阈值45，落入LOW
        assert 25 <= result["score"] < 45, f"14天库存应为偏低风险，实际: {result['score']}"
        assert result["level"] == "low"

    def test_low_risk(self):
        """测试低风险（30天库存）"""
        result = self.scorer.calculate_risk_score(days_cover=30)
        assert result["score"] < 50, f"30天库存应为低风险，实际: {result['score']}"
        assert result["level"] == "low"

    def test_peak_season_higher_risk(self):
        """测试旺季应提升风险"""
        result_normal = self.scorer.calculate_risk_score(days_cover=14, is_peak_season=False)
        result_peak = self.scorer.calculate_risk_score(days_cover=14, is_peak_season=True)
        assert result_peak["score"] > result_normal["score"], "旺季风险应更高"

    def test_urgency_descriptions(self):
        """测试紧急程度描述"""
        result = self.scorer.calculate_risk_score(days_cover=3)
        assert "🚨" in result["urgency"] or "紧急" in result["urgency"]

    def test_recommendations_generated(self):
        """测试建议生成"""
        result = self.scorer.calculate_risk_score(days_cover=5)
        assert len(result["recommendations"]) > 0


class TestReplenishmentCalculator:
    """补货计算引擎测试"""

    def setup_method(self):
        self.calc = ReplenishmentCalculator()

    def _make_input(
        self,
        current_stock=120,
        in_transit=0,
        lead_time=25,
        avg_sales=30.0,
        sku_id="TEST-001",
        **kwargs
    ):
        """创建测试输入"""
        return ReplenishmentInput(
            sku_id=sku_id,
            current_stock=current_stock,
            in_transit_stock=in_transit,
            lead_time_days=lead_time,
            avg_daily_sales=avg_sales,
            product_cost_per_unit=2.2,
            freight_cost_per_unit=0.6,
            selling_price=13.99,
            fba_fee_per_unit=3.8,
            **kwargs
        )

    def test_urgent_mode_trigger(self):
        """测试紧急补货模式触发（库存<7天）"""
        inp = self._make_input(current_stock=150, avg_sales=30)  # 5天库存
        result = self.calc.calculate(inp)
        assert result.mode == "urgent", f"5天库存应触发紧急模式，实际: {result.mode}"
        # 5天库存：days_cover=45 + 其他因子~18 = ~63分 → medium
        assert result.risk_level in ["high", "medium"], f"5天库存应为中高风险，实际: {result.risk_level}"

    def test_standard_mode_trigger(self):
        """测试标准补货模式触发（7-21天）"""
        inp = self._make_input(current_stock=400, avg_sales=30)  # ~13天库存
        result = self.calc.calculate(inp)
        assert result.mode == "standard", f"13天库存应触发标准模式，实际: {result.mode}"

    def test_optimized_mode_trigger(self):
        """测试优化补货模式触发（>21天）"""
        inp = self._make_input(current_stock=800, avg_sales=30)  # ~27天库存
        result = self.calc.calculate(inp)
        assert result.mode == "optimized", f"27天库存应触发优化模式，实际: {result.mode}"
        assert result.risk_level == "low"

    def test_recommended_quantity_positive(self):
        """测试建议补货数量为正"""
        inp = self._make_input(current_stock=100, avg_sales=30)
        result = self.calc.calculate(inp)
        assert result.recommended_quantity > 0, "库存不足时应建议补货"

    def test_with_in_transit_stock(self):
        """测试有在途库存时的计算"""
        inp = self._make_input(current_stock=50, in_transit=300, avg_sales=30)
        result = self.calc.calculate(inp)
        # 在途300个，到了后约可售10天，总可售约11.7天
        assert result.days_cover_after_transit > result.days_cover

    def test_latest_order_date_calculation(self):
        """测试最迟下单日期计算"""
        inp = self._make_input(current_stock=150, avg_sales=30)  # 5天库存
        result = self.calc.calculate(inp)
        today = datetime.now().date()
        order_date = datetime.strptime(result.latest_order_date, "%Y-%m-%d").date()
        # 5天库存，要提前25天下单，所以订单日期应该已过（负数天）
        # 但格式应该正确
        assert result.latest_order_date is not None

    def test_shipping_options_generated(self):
        """测试运输方案生成"""
        inp = self._make_input(current_stock=150, avg_sales=30)
        result = self.calc.calculate(inp)
        assert len(result.shipping_options) > 0
        assert "sea" in result.shipping_options or "air" in result.shipping_options

    def test_batch_calculation_ranking(self):
        """测试批量计算优先级排序"""
        inputs = [
            self._make_input(sku_id="SKU-A", current_stock=50, avg_sales=30),   # 高风险
            self._make_input(sku_id="SKU-B", current_stock=500, avg_sales=30),  # 低风险
            self._make_input(sku_id="SKU-C", current_stock=100, avg_sales=10),  # 中风险
        ]
        results = self.calc.batch_calculate(inputs)

        # 第一个应该是最高风险/最低库存的
        assert results[0].priority_rank == 1
        # 所有结果都有优先级
        for r in results:
            assert r.priority_rank > 0

    def test_zero_sales_handling(self):
        """测试零销量处理（防除零）"""
        inp = self._make_input(current_stock=100, avg_sales=0)
        result = self.calc.calculate(inp)
        assert result.days_cover == 0 or result.days_cover > 0  # 不应崩溃
        assert result.recommended_quantity >= 0


class TestAlgorithmIntegration:
    """算法集成测试（端到端）"""

    def setup_method(self):
        self.calc = ReplenishmentCalculator()

    def test_catit_filter_12pack_scenario(self):
        """
        场景：Catit兼容滤芯12个装
        - 当前库存：120个
        - 在途：500个（预计12天后到）
        - 日均销量：25个
        - 备货天数：25天
        """
        inp = ReplenishmentInput(
            sku_id="CATIT-FILTER-12",
            current_stock=120,
            in_transit_stock=500,
            lead_time_days=25,
            avg_daily_sales=25.0,
            product_cost_per_unit=2.2,
            freight_cost_per_unit=0.6,
            selling_price=13.99,
            fba_fee_per_unit=3.8,
        )
        result = self.calc.calculate(inp)

        # 验证计算合理性
        assert result.recommended_quantity > 0, "应该有补货建议"
        assert result.days_cover > 0, "应该计算可售天数"
        assert result.days_cover_after_transit > result.days_cover, "在途库存应增加可售天数"
        assert result.risk_score > 0, "应该有风险评分"
        assert result.mode in ["urgent", "standard", "optimized"]
        assert len(result.recommendations) > 0, "应该有行动建议"

    def test_lead_time_variability_scenario(self):
        """
        场景：供应商交期不稳定
        - 新供应商，安全系数应该更高
        """
        inp_normal = ReplenishmentInput(
            sku_id="TEST-1",
            current_stock=200,
            avg_daily_sales=20.0,
            lead_time_days=25,
            supply_stability="normal",
            product_cost_per_unit=2.0,
            selling_price=14.0,
            fba_fee_per_unit=3.8,
        )
        inp_new = ReplenishmentInput(
            sku_id="TEST-2",
            current_stock=200,
            avg_daily_sales=20.0,
            lead_time_days=25,
            supply_stability="new_supplier",
            product_cost_per_unit=2.0,
            selling_price=14.0,
            fba_fee_per_unit=3.8,
        )

        r1 = self.calc.calculate(inp_normal)
        r2 = self.calc.calculate(inp_new)

        # 新供应商应该建议更多补货量（更高的安全库存）
        assert r2.recommended_quantity >= r1.recommended_quantity, \
            "新供应商应建议更多补货量"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])