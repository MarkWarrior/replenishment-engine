"""
SKU管理页面
CRUD：添加、查看、编辑SKU
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth_ui import api_get, api_post, api_put, api_delete, require_auth

# 强制认证
tenant_id = require_auth()

API_BASE = "http://localhost:8000"


def get_all_skus():
    r = api_get(f"{API_BASE}/api/skus?is_active=true")
    if r.status_code == 200:
        return r.json()
    return []


def create_sku(data):
    r = api_post(f"{API_BASE}/api/skus", json=data)
    return r.status_code, r.json() if r.status_code < 400 else {"detail": r.text}


def update_sku(sku_code, data):
    r = api_put(f"{API_BASE}/api/skus/{sku_code}", json=data)
    return r.status_code, r.json() if r.status_code < 400 else {"detail": r.text}


def create_inventory(sku_code, data):
    r = api_post(f"{API_BASE}/api/inventory/{sku_code}", json=data)
    return r.status_code, r.json() if r.status_code < 400 else {"detail": r.text}


# ============================================================
# 页面
# ============================================================
st.title("📋 SKU管理")
st.caption("产品信息维护 · 库存录入")

tab_list, tab_add, tab_detail = st.tabs(["📋 列表", "➕ 添加SKU", "🔍 详情"])

# ============================================================
# 列表页
# ============================================================
with tab_list:
    skus = get_all_skus()

    if skus:
        df = pd.DataFrame([{
            "SKU编码": s["sku_code"],
            "产品名称": s["product_name"],
            "ASIN": s.get("asin", "-"),
            "成本": f"${s['product_cost']:.2f}",
            "售价": f"${s['selling_price']:.2f}",
            "FBA费": f"${s['fba_fee']:.2f}",
            "备货天数": f"{s['lead_time_days']}天",
            "供应链": s["supply_stability"],
            "安全系数": f"{s['safety_factor']:.2f}",
        } for s in skus])

        st.dataframe(df, use_container_width=True, hide_index=True, height=400)
    else:
        st.info("暂无SKU数据，请点击「添加SKU」创建第一个产品")

# ============================================================
# 添加SKU页
# ============================================================
with tab_add:
    st.subheader("创建新SKU")

    with st.form("create_sku_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            sku_code = st.text_input("SKU编码 *", placeholder="如: CATIT-FILTER-12")
            product_name = st.text_input("产品名称 *", placeholder="如: Catit兼容滤芯12个装")
            asin = st.text_input("ASIN", placeholder="可选")

        with col2:
            product_cost = st.number_input("产品成本 (美元)", min_value=0.0, value=0.0, step=0.1)
            freight_cost = st.number_input("单个运费 (美元)", min_value=0.0, value=0.0, step=0.1)
            fba_fee = st.number_input("FBA费用/个", min_value=0.0, value=0.0, step=0.1)

        col3, col4 = st.columns(2)
        with col3:
            selling_price = st.number_input("售价 (美元)", min_value=0.0, value=0.0, step=0.1)
            lead_time_days = st.number_input("备货天数", min_value=1, value=25)

        with col4:
            supply_stability = st.select_slider(
                "供应链稳定性",
                options=["stable", "normal", "unstable", "new_supplier"],
                value="normal",
            )
            safety_factor = st.number_input("安全系数", min_value=1.0, max_value=2.0, value=1.15, step=0.05)

        submitted = st.form_submit_button("💾 创建SKU", use_container_width=True)

        if submitted:
            if not sku_code or not product_name:
                st.error("SKU编码和产品名称为必填项")
            else:
                data = {
                    "sku_code": sku_code,
                    "product_name": product_name,
                    "asin": asin if asin else None,
                    "product_cost": product_cost,
                    "freight_cost": freight_cost,
                    "fba_fee": fba_fee,
                    "selling_price": selling_price,
                    "lead_time_days": lead_time_days,
                    "supply_stability": supply_stability,
                    "safety_factor": safety_factor,
                }
                status, resp = create_sku(data)
                if status == 201:
                    st.success(f"✅ SKU {sku_code} 创建成功！")
                else:
                    st.error(f"创建失败: {resp.get('detail', resp)}")

# ============================================================
# 详情页
# ============================================================
with tab_detail:
    st.subheader("录入库存 & 查看详情")

    skus = get_all_skus()
    if not skus:
        st.info("暂无SKU数据")
    else:
        selected = st.selectbox("选择SKU", options=[s["sku_code"] for s in skus])

        sku_info = next((s for s in skus if s["sku_code"] == selected), None)
        if sku_info:
            col1, col2 = st.columns(2)
            col1.markdown(f"**产品名称：** {sku_info['product_name']}")
            col2.markdown(f"**ASIN：** {sku_info.get('asin', '-')}")

            col1, col2, col3 = st.columns(3)
            col1.metric("成本", f"${sku_info['product_cost']:.2f}")
            col2.metric("售价", f"${sku_info['selling_price']:.2f}")
            col3.metric("FBA费", f"${sku_info['fba_fee']:.2f}")

            col1, col2, col3 = st.columns(3)
            col1.metric("备货天数", f"{sku_info['lead_time_days']}天")
            col2.metric("供应链", sku_info['supply_stability'])
            col3.metric("安全系数", f"{sku_info['safety_factor']:.2f}")

            st.divider()
            st.subheader("📦 录入库存")

            with st.form("inventory_form", clear_on_submit=True):
                col_i1, col_i2 = st.columns(2)
                with col_i1:
                    current_stock = st.number_input("当前在库库存 *", min_value=0, value=0)
                with col_i2:
                    in_transit = st.number_input("在途库存", min_value=0, value=0)

                notes = st.text_area("备注", placeholder="可选")

                inv_submitted = st.form_submit_button("📦 提交库存", use_container_width=True)

                if inv_submitted:
                    if current_stock <= 0:
                        st.error("当前库存必须大于0")
                    else:
                        data = {
                            "current_stock": current_stock,
                            "in_transit_stock": in_transit,
                            "notes": notes if notes else None,
                        }
                        status, resp = create_inventory(selected, data)
                        if status == 201:
                            st.success("✅ 库存录入成功！")
                        else:
                            st.error(f"录入失败: {resp.get('detail', resp)}")