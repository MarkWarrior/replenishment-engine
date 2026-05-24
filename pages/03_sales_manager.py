"""
销量管理页面
CSV导入销量数据 + 查看历史
"""

import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth_ui import api_get, api_post, api_post_files, require_auth

# 强制认证
tenant_id = require_auth()

API_BASE = "http://localhost:8000"


def get_all_skus():
    r = api_get(f"{API_BASE}/api/skus?is_active=true")
    if r.status_code == 200:
        return r.json()
    return []


def import_sales_csv(sku_code, file):
    files = {"file": (file.name, file.getvalue(), "text/csv")}
    r = api_post_files(f"{API_BASE}/api/sales/{sku_code}/import_csv", files=files)
    return r.status_code, r.json() if r.status_code < 400 else {"detail": r.text}


def get_sales_history(sku_code, days=30):
    r = api_get(f"{API_BASE}/api/sales/{sku_code}/history", params={"days": days})
    if r.status_code == 200:
        return r.json()
    return []


# ============================================================
# 页面
# ============================================================
st.title("📈 销量管理")
st.caption("CSV导入销量历史数据 · 查看趋势")

tab_import, tab_history = st.tabs(["📤 CSV导入", "📊 历史数据"])

# ============================================================
# CSV导入
# ============================================================
with tab_import:
    st.subheader("CSV批量导入销量")

    skus = get_all_skus()
    if not skus:
        st.warning("暂无可用SKU，请先在 SKU管理 添加产品")
    else:
        sku_options = {s["sku_code"]: s["product_name"] for s in skus}
        selected_sku = st.selectbox("选择SKU", options=list(sku_options.keys()),
                                    format_func=lambda x: f"{x} - {sku_options[x]}")

        st.info("""
        **CSV格式要求（第一行必须为表头）：**

        ```
        date,quantity_sold,unit_price
        2026-05-01,12,13.99
        2026-05-02,8,13.99
        ```

        - `date`：日期，格式 `YYYY-MM-DD`
        - `quantity_sold`：当日销量（整数）
        - `unit_price`：单价（可选，美元）
        """)

        uploaded_file = st.file_uploader("上传CSV文件", type=["csv"])

        if uploaded_file:
            st.write(f"**文件：** {uploaded_file.name} （{uploaded_file.size:,} bytes）")

            if st.button("🚀 开始导入", type="primary", use_container_width=True):
                with st.spinner("导入中..."):
                    status, resp = import_sales_csv(selected_sku, uploaded_file)

                if status == 201:
                    st.success(f"✅ 导入完成！成功 {resp['success_count']} 条，跳过 {resp['skip_count']} 条（去重或格式错误）")
                    if resp["errors"]:
                        with st.expander("⚠️ 查看错误详情"):
                            for err in resp["errors"]:
                                st.write(f"- {err}")
                else:
                    st.error(f"❌ 导入失败：{resp.get('detail', resp)}")

# ============================================================
# 历史数据
# ============================================================
with tab_history:
    st.subheader("销量历史趋势")

    skus = get_all_skus()
    if not skus:
        st.warning("暂无数据")
    else:
        col_sel, col_days = st.columns([1, 1])
        with col_sel:
            sku_options = {s["sku_code"]: s["product_name"] for s in skus}
            selected_sku = st.selectbox("选择SKU", options=list(sku_options.keys()),
                                        format_func=lambda x: f"{x} - {sku_options[x]}",
                                        key="history_sku")

        with col_days:
            days = st.select_slider("查看周期", options=[7, 14, 30, 60, 90], value=30)

        records = get_sales_history(selected_sku, days=days)

        if records:
            df = pd.DataFrame([{
                "日期": r["sale_date"][:10],
                "销量": r["quantity_sold"],
                "单价": f"${r['unit_price']:.2f}" if r["unit_price"] else "-",
            } for r in records])

            col1, col2 = st.columns(2)
            total_sales = sum(r["quantity_sold"] for r in records)
            avg_sales = total_sales / len(records) if records else 0
            col1.metric("总销量", f"{total_sales:,} 个")
            col2.metric("日均销量", f"{avg_sales:.1f} 个/天")

            st.dataframe(df.sort_values("日期", ascending=False),
                        use_container_width=True, hide_index=True)

            # 简单折线图
            chart_data = df.sort_values("日期").set_index("日期")
            st.line_chart(chart_data["销量"])
        else:
            st.info("暂无销量数据，请先导入CSV")