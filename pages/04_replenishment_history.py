"""
补货历史记录页面
查看所有SKU的补货记录，支持筛选和标记收货
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from app.auth_ui import api_get, api_put, require_auth

# 强制认证
tenant_id = require_auth()

API_BASE = "http://localhost:8000"


def get_all_skus():
    r = api_get(f"{API_BASE}/api/skus?is_active=true")
    if r.status_code == 200:
        return r.json()
    return []


def get_replenishment_history(sku_code, limit=50):
    r = api_get(f"{API_BASE}/api/replenishment/{sku_code}/history")
    if r.status_code == 200:
        return r.json()
    return []


def mark_received(record_id, quantity):
    r = api_put(f"{API_BASE}/api/replenishment/{record_id}/receive",
                json={"quantity_received": quantity})
    return r.status_code == 200


st.title("📋 补货历史")
st.caption("查看补货记录 · 标记收货状态")

# ============================================================
# 筛选条件
# ============================================================
skus = get_all_skus()

col_sku, col_status = st.columns([1, 1])

with col_sku:
    sku_options = {"ALL": "全部SKU"} | {s["sku_code"]: s["product_name"] for s in skus}
    selected_key = st.selectbox("筛选SKU", options=list(sku_options.keys()),
                                format_func=lambda x: f"{x} - {sku_options[x]}")

with col_status:
    status_options = ["ALL", "pending", "in_transit", "delivered", "cancelled"]
    selected_status = st.selectbox("订单状态", options=status_options,
                                   format_func=lambda x: x.upper() if x != "ALL" else "全部状态")

# ============================================================
# 加载数据
# ============================================================
all_records = []

if selected_key == "ALL":
    target_skus = skus
else:
    target_skus = [s for s in skus if s["sku_code"] == selected_key]

for sku in target_skus:
    history = get_replenishment_history(sku["sku_code"], limit=100)
    for h in history:
        h["product_name"] = sku["product_name"]
    all_records.extend(history)

# 状态筛选
if selected_status != "ALL":
    all_records = [r for r in all_records if r["status"] == selected_status]

# ============================================================
# 统计卡片
# ============================================================
if all_records:
    total_cost = sum(r["total_cost"] for r in all_records)
    pending_count = sum(1 for r in all_records if r["status"] in ["pending", "in_transit"])
    delivered_count = sum(1 for r in all_records if r["status"] == "delivered")

    col1, col2, col3 = st.columns(3)
    col1.metric("总记录数", len(all_records))
    col2.metric("待收货", pending_count, delta="需跟进" if pending_count > 0 else None, delta_color="inverse")
    col3.metric("已完成", delivered_count)

    st.divider()

# ============================================================
# 表格
# ============================================================
if all_records:
    df = pd.DataFrame([{
        "ID": r["id"],
        "SKU": r["sku_code"],
        "产品名称": r.get("product_name", "-"),
        "下单日期": r["order_date"][:10] if r["order_date"] else "-",
        "预计到货": r["expected_arrival_date"][:10] if r["expected_arrival_date"] else "-",
        "实收到货": r["actual_arrival_date"][:10] if r["actual_arrival_date"] else "-",
        "补货量": f"{r['quantity_ordered']:,}",
        "实收量": f"{r['quantity_received']:,}",
        "总成本": f"${r['total_cost']:,.2f}",
        "风险分": r["risk_score"],
        "模式": r["mode"],
        "状态": r["status"],
    } for r in all_records])

    # 状态颜色
    status_colors = {
        "pending": "⏳ 待处理",
        "in_transit": "🚢 运输中",
        "delivered": "✅ 已完成",
        "cancelled": "❌ 已取消",
    }
    df["状态"] = df["状态"].map(lambda x: status_colors.get(x, x))

    st.dataframe(df.sort_values("下单日期", ascending=False),
                 use_container_width=True, hide_index=True, height=400)
else:
    st.info("暂无补货记录")

# ============================================================
# 标记收货
# ============================================================
st.divider()
st.subheader("📦 标记收货")

col_rec_id, col_sku_disp, col_qty, col_btn = st.columns([1, 1, 1, 1])

with col_rec_id:
    if all_records:
        pending_records = [r for r in all_records if r["status"] in ["pending", "in_transit"]]
        if pending_records:
            rec_options = {r["id"]: f"#{r['id']} {r['sku_code']}" for r in pending_records}
            selected_rec_id = st.selectbox("选择记录", options=list(rec_options.keys()),
                                            format_func=lambda x: rec_options[x])
        else:
            selected_rec_id = None
            st.caption("暂无待收货记录")
    else:
        selected_rec_id = None

if selected_rec_id:
    with col_sku_disp:
        rec = next(r for r in all_records if r["id"] == selected_rec_id)
        st.caption(f"📦 {rec['sku_code']}")

    with col_qty:
        receive_qty = st.number_input("实收数量", min_value=0, value=rec["quantity_ordered"], key="rcv_qty")

    with col_btn:
        st.write("")
        if st.button("✅ 确认收货", type="secondary", use_container_width=True):
            if mark_received(selected_rec_id, receive_qty):
                st.success("✅ 标记成功！")
                st.rerun()
            else:
                st.error("❌ 标记失败")