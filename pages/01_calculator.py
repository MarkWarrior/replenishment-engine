"""
补货计算器页面
输入SKU → 查看详细补货建议
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth_ui import api_get, api_post, api_put, require_auth

# 强制认证
tenant_id = require_auth()

API_BASE = "http://localhost:8000"


def get_all_skus():
    r = api_get(f"{API_BASE}/api/skus?is_active=true")
    if r.status_code == 200:
        return r.json()
    return []


def calculate_replenishment(sku_code, current_stock=None, in_transit_stock=None, avg_daily_sales=None):
    payload = {"sku_code": sku_code}
    if current_stock is not None:
        payload["current_stock"] = current_stock
    if in_transit_stock is not None:
        payload["in_transit_stock"] = in_transit_stock
    if avg_daily_sales is not None:
        payload["avg_daily_sales"] = avg_daily_sales

    try:
        r = api_post(f"{API_BASE}/api/replenishment/calculate", json=payload)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def get_current_inventory(sku_code):
    try:
        r = api_get(f"{API_BASE}/api/inventory/{sku_code}")
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


# ============================================================
# 页面
# ============================================================
st.title("🧮 补货计算器")
st.caption("基于实时库存和销量数据，智能计算补货建议")

# ============================================================
# SKU选择 + 参数输入
# ============================================================
st.subheader("1️⃣ 选择产品")

col_select, col_param = st.columns([1, 1])

with col_select:
    skus = get_all_skus()
    sku_options = {s["sku_code"]: s["product_name"] for s in skus}
    selected_sku = st.selectbox("选择SKU", options=list(sku_options.keys()),
                                 format_func=lambda x: f"{x} - {sku_options[x]}")

    # 自动填充最新库存
    inv = get_current_inventory(selected_sku)
    current_inv_stock = inv["current_stock"] if inv else 0
    current_in_transit = inv["in_transit_stock"] if inv else 0
    current_days_cover = inv["days_cover"] if inv else 0

with col_param:
    st.write("覆盖默认参数（可选）")
    override_stock = st.number_input("当前库存", value=current_inv_stock, min_value=0)
    override_transit = st.number_input("在途库存", value=current_in_transit, min_value=0)

# ============================================================
# 计算按钮
# ============================================================
if st.button("🚀 计算补货建议", type="primary", use_container_width=True):
    result = calculate_replenishment(
        selected_sku,
        current_stock=override_stock,
        in_transit_stock=override_transit,
    )

    if result:
        st.session_state["calc_result"] = result
    else:
        st.error("计算失败，请检查API服务是否启动")

# ============================================================
# 显示结果
# ============================================================
if "calc_result" in st.session_state and st.session_state["calc_result"]:
    result = st.session_state["calc_result"]

    st.divider()
    st.subheader("2️⃣ 补货建议结果")

    # 风险等级颜色
    risk_colors = {"high": "🔴 高风险", "medium": "🟡 中风险", "low": "🟢 低风险"}
    mode_labels = {"urgent": "🚨 紧急补货", "standard": "⚠️ 标准补货", "optimized": "✅ 优化补货"}

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("建议补货数量", f"{result['recommended_quantity']:,} 个")
    col2.metric("补货模式", mode_labels.get(result["mode"], result["mode"]))
    col3.metric("风险等级", risk_colors.get(result["risk_level"], result["risk_level"]))
    col4.metric("风险评分", f"{result['risk_score']} 分")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("当前库存", f"{result['current_stock']:,} 个")
    col6.metric("在途库存", f"{result['in_transit_stock']:,} 个")
    col7.metric("可售天数", f"{result['days_cover']:.1f} 天")
    col8.metric("到仓后可售", f"{result['days_cover_after_transit']:.1f} 天")

    col9, col10, col11, col12 = st.columns(4)
    col9.metric("预计补货成本", f"${result['estimated_cost']:,.2f}")
    col10.metric("预计利润增量", f"${result['estimated_profit']:,.2f}")
    col11.metric("最迟下单日", result["latest_order_date"])
    col12.metric("预计到仓日", result["estimated_arrival_date"])

    # ============================================================
    # 行动建议
    # ============================================================
    st.divider()
    st.subheader("3️⃣ 行动建议")

    for rec in result["recommendations"]:
        st.success(rec)

    # ============================================================
    # 运输方案对比
    # ============================================================
    if result["shipping_options"]:
        st.divider()
        st.subheader("🚢 运输方案对比")

        shipping_data = []
        for mode, info in result["shipping_options"].items():
            rec_label = "✅ 推荐" if info.get("recommended") else "⬜"
            arrive_label = "✅ 能到" if info.get("arrive_before_stockout") else "❌ 来不及"
            shipping_data.append({
                "方案": info["name"],
                "时效": f"{info['days']}天",
                "单价": f"${info['cost_per_unit']:.2f}",
                "总成本": f"${info['total_cost']:,.2f}",
                "准时到达": arrive_label,
                "推荐": rec_label,
            })

        df_ship = pd.DataFrame(shipping_data)
        st.dataframe(df_ship, hide_index=True, use_container_width=True)

    # ============================================================
    # 保存补货决策
    # ============================================================
    st.divider()
    st.subheader("4️⃣ 保存补货决策")

    shipping_options = list(result.get("shipping_options", {}).keys())
    if not shipping_options:
        shipping_options = ["sea", "air", "express"]

    selected_shipping = st.selectbox(
        "选择运输方案",
        options=shipping_options,
        format_func=lambda x: f"{x.upper()}",
        key="shipping_select",
    )

    col_save, col_status = st.columns([1, 2])
    with col_save:
        save_key = f"save_btn_{selected_sku}"
        if st.button("💾 保存补货决策", type="primary", use_container_width=True, key=save_key):
            shipping_info = result["shipping_options"].get(selected_shipping, {})
            expected_days = shipping_info.get("days", 25)

            payload = {
                "recommended_quantity": result["recommended_quantity"],
                "mode": result["mode"],
                "shipping_method": selected_shipping,
                "expected_arrival_days": expected_days,
                "total_cost": result["estimated_cost"],
                "risk_score": result["risk_score"],
                "days_cover_at_order": result["days_cover"],
            }

            try:
                r = api_post(f"{API_BASE}/api/replenishment/{selected_sku}/save", json=payload)
                if r.status_code == 201:
                    st.session_state["saved_record"] = r.json()
                    st.success("✅ 补货决策已保存！")
                else:
                    st.error(f"❌ 保存失败：{r.json().get('detail', r.text)}")
            except Exception as e:
                st.error(f"❌ 保存失败：{e}")

    if "saved_record" in st.session_state:
        rec = st.session_state["saved_record"]
        with col_status:
            st.info(
                f"📋 已保存记录 #ID: {rec['id']} | "
                f"下单日: {rec['order_date'][:10]} | "
                f"预计到货: {rec['expected_arrival_date'][:10]}"
            )

    # ============================================================
    # 补货历史记录
    # ============================================================
    st.divider()
    st.subheader("📜 最近补货记录")

    try:
        r = api_get(f"{API_BASE}/api/replenishment/{selected_sku}/history")
        if r.status_code == 200:
            history = r.json()
            if history:
                hist_df = pd.DataFrame([{
                    "ID": h["id"],
                    "下单日期": h["order_date"][:10],
                    "预计到货": h["expected_arrival_date"][:10] if h["expected_arrival_date"] else "-",
                    "实收到货": h["actual_arrival_date"][:10] if h["actual_arrival_date"] else "-",
                    "补货量": f"{h['quantity_ordered']:,}",
                    "实收量": f"{h['quantity_received']:,}",
                    "总成本": f"${h['total_cost']:,.2f}",
                    "模式": h["mode"],
                    "状态": h["status"],
                } for h in history])

                st.dataframe(hist_df, hide_index=True, use_container_width=True, height=200)

                # 标记收货
                st.subheader("📦 标记收货")
                col_rec_id, col_qty, col_btn = st.columns([1, 1, 1])
                with col_rec_id:
                    rec_ids = [h["id"] for h in history if h["status"] != "delivered"]
                    if rec_ids:
                        selected_id = st.selectbox("选择记录", options=rec_ids, key="receive_id")
                    else:
                        selected_id = None
                        st.caption("暂无待收货记录")

                if selected_id:
                    with col_qty:
                        receive_qty = st.number_input("实收数量", min_value=0, key="receive_qty")
                    with col_btn:
                        st.write("")  # 对齐
                        if st.button("📦 标记已到货", type="secondary", use_container_width=True):
                            try:
                                rr = api_put(
                                    f"{API_BASE}/api/replenishment/{selected_id}/receive",
                                    json={"quantity_received": receive_qty},
                                )
                                if rr.status_code == 200:
                                    st.success("✅ 标记成功！")
                                    st.rerun()
                                else:
                                    st.error(f"❌ 失败：{rr.json().get('detail', rr.text)}")
                            except Exception as e:
                                st.error(f"❌ 失败：{e}")
            else:
                st.info("暂无补货历史记录")
        else:
            st.warning("获取历史记录失败")
    except Exception as e:
        st.error(f"获取历史记录失败：{e}")