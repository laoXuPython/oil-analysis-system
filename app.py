# ============================================================
# app.py —— 油料数据智能分析系统（Streamlit 可视化界面）
# 依赖：streamlit, pandas, core, data_analysis
# 运行：streamlit run app.py
# ============================================================

import os
from datetime import datetime

import pandas as pd
import streamlit as st

from core import OilTransaction
from data_analysis import DataManager, StatisticsAnalyzer

# ---------- 首次启动引导：无台账数据时自动生成演示数据 ----------
def _bootstrap_demo_data():
    need = True
    if os.path.exists("oil_record.csv"):
        with open("oil_record.csv", encoding="utf-8-sig") as f:
            need = sum(1 for _ in f) <= 1  # 只有表头也算空
    if need:
        import generate_mock_data
        generate_mock_data.generate_demo_data()

_bootstrap_demo_data()

# ---------- 页面设置 ----------
st.set_page_config(page_title="油料数据智能分析系统", layout="wide")

# ---------- 访问密码（可选） ----------
# 部署到公网后，在 Streamlit Cloud 的 Secrets 中配置 APP_PASSWORD 即可开启；
# 不配置则不启用密码，任何人都可访问。本地运行时无需任何设置。
try:
    _app_pwd = st.secrets.get("APP_PASSWORD", "")
except Exception:
    _app_pwd = ""  # 本地无 secrets 文件时不启用密码
if _app_pwd:
    if not st.session_state.get("authed"):
        st.title("🛢️ 军民融合油料数据智能分析系统")
        pwd = st.text_input("请输入访问密码", type="password")
        if pwd == _app_pwd:
            st.session_state["authed"] = True
            st.rerun()
        elif pwd:
            st.error("密码错误，请重试")
        st.stop()

st.title("🛢️ 军民融合油料数据智能分析系统")
st.markdown("---")

# ---------- 侧边栏：全局信息 ----------
st.sidebar.header("系统状态")
df_sidebar = DataManager.load_all()
st.sidebar.metric("累计交易笔数", len(df_sidebar))

# 检查是否存在 tank_snapshot.csv，显示最近快照日期
snap_file = "tank_snapshot.csv"
if os.path.exists(snap_file):
    snap_df = pd.read_csv(snap_file, encoding='utf-8-sig')
    if not snap_df.empty:
        latest_snap = snap_df['快照日期'].max()
        st.sidebar.metric("最近罐存快照", latest_snap)

st.sidebar.markdown("---")
st.sidebar.info("💡 提示：本地首次使用请先运行 `generate_mock_data.py` 生成模拟数据。")

# ---------- 三个功能页签 ----------
tab1, tab2, tab3 = st.tabs(["📝 数据录入", "📋 历史查询", "📊 统计分析"])

# ==================== 页签1：数据录入 ====================
with tab1:
    st.header("单笔油料收发录入")
    st.markdown("输入作业参数，系统自动计算损耗并判定合规性，结果存入电子台账。")

    # 输入表单
    with st.form("input_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            oil_type = st.selectbox("油品类型", ["柴油", "汽油"])
            density_20 = st.number_input("标准密度 (kg/m³)", value=835.0 if oil_type == "柴油" else 745.0, step=1.0)
        with col2:
            issue_vol = st.number_input("发油体积 (m³)", value=12000.0, step=100.0)
            temp = st.number_input("实测油温 (℃)", value=25.0, step=0.5)
        with col3:
            control_factor = st.slider("管理控制系数", 0.5, 1.0, 0.8, 0.1)
            actual_loaded = st.number_input("实际装车吨位 (吨)", value=0.0, step=0.1)
            actual_received = st.number_input("实际收油吨位 (吨)", value=0.0, step=0.1)

        submitted = st.form_submit_button("开始计算并保存")

    if submitted:
        # 参数校验
        if actual_loaded <= 0 or actual_received <= 0:
            st.error("实际装车吨位和收油吨位必须大于0")
        else:
            # 调用核心计算
            deal = OilTransaction(oil_type, density_20, control_factor)
            full = deal.full_chain_calc(issue_vol=issue_vol, temp=temp)
            issue_mass = full["计算所得发油量(吨)"]  # 理论发油质量
            check = deal.check_actual_vs_theory(issue_mass, actual_loaded, actual_received)

            # 生成交易编号和时间
            now = datetime.now()
            transaction_id = f"OIL-{now.strftime('%Y%m%d%H%M%S')}"
            transaction_time = now.strftime('%Y-%m-%d %H:%M:%S')

            # 存入台账
            DataManager.save_transaction(
                transaction_id, transaction_time,
                oil_type, density_20, temp, issue_vol,
                issue_mass, full["发油损耗(吨)"], full["装车量(吨)"],
                full["运输损耗(吨)"], full["到货量(吨)"], full["收油损耗(吨)"],
                full["最低允收量(吨)"], control_factor,
                actual_loaded, actual_received,
                check["发油端判定"], check["收油端判定"]
            )

            # 显示结果
            st.success("✅ 计算完成，数据已存入台账")

            # 新增：显示本次核算发油量（理论出库质量）
            st.info(f"📌 本次核算发油量：**{issue_mass:.3f} 吨** (基于体积 {issue_vol} m³ / 油温 {temp} ℃)")

            col_r1, col_r2 = st.columns(2)
            with col_r1:
                st.subheader("📏 管理控制损耗")
                control = deal.calc_control_limits(issue_mass)
                st.write(f"发油：国标 {control['国标发油损耗(吨)']:.3f}t → 控制 ≤{control['控制发油损耗(吨)']:.3f}t")
                st.write(f"运输：国标 {control['国标运输损耗(吨)']:.3f}t → 控制 ≤{control['控制运输损耗(吨)']:.3f}t")
                st.write(f"收油：国标 {control['国标收油损耗(吨)']:.3f}t → 控制 ≤{control['控制收油损耗(吨)']:.3f}t")
            with col_r2:
                st.subheader("📊 验收判定")
                st.write(f"理论装车：{check['理论应装车(吨)']:.3f}t，实际：{actual_loaded}t → **{check['发油端判定']}**")
                st.write(
                    f"理论最低允收：{check['理论最低允收(吨)']:.3f}t，实际：{actual_received}t → **{check['收油端判定']}**"
                )

# ==================== 页签2：历史查询 ====================
with tab2:
    st.header("历史台账查询")
    st.markdown("支持按日期范围、油品类型、异常状态筛选交易记录。")

    # 每次渲染页签时重新读取台账，保证刚录入的数据立即可查
    df_all = DataManager.load_all()

    col_q1, col_q2 = st.columns(2)
    with col_q1:
        query_type = st.radio("查询方式", ["全部记录", "按日期范围", "仅异常记录"], horizontal=True)
    with col_q2:
        if query_type == "按日期范围":
            start_date = st.date_input("开始日期", datetime(2026, 3, 1))
            end_date = st.date_input("结束日期", datetime(2026, 5, 31))

    # 执行查询
    if query_type == "全部记录":
        result_df = df_all
    elif query_type == "按日期范围":
        result_df = DataManager.query_by_date(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    else:
        result_df = DataManager.query_abnormal()

    # 油品筛选
    if not result_df.empty:
        oil_filter = st.multiselect(
            "按油品筛选",
            options=result_df["油品类型"].unique(),
            default=result_df["油品类型"].unique()
        )
        result_df = result_df[result_df["油品类型"].isin(oil_filter)]

    st.subheader(f"查询结果（共 {len(result_df)} 条）")
    if not result_df.empty:
        # 展示关键列
        show_cols = ["交易编号", "交易时间", "油品类型", "核算发油量(吨)", "发油判定", "收油判定"]
        st.dataframe(result_df[show_cols].reset_index(drop=True), use_container_width=True)
    else:
        st.info("没有符合条件的记录。")

# ==================== 页签3：统计分析 ====================
with tab3:
    st.header("油料数据统计分析")
    st.markdown("基于全量台账数据，展示基础指标、分油品统计及月度趋势。")

    # 每次渲染页签时重新读取台账，保证统计口径为最新数据
    df_all = DataManager.load_all()

    if df_all.empty:
        st.warning("台账为空，请先生成数据或录入作业。")
    else:
        analyzer = StatisticsAnalyzer(df_all)

        # 基础统计卡片
        st.subheader("📈 基础统计")
        stats = analyzer.get_basic_stats()
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            st.metric("总记录数", stats["总记录数"])
        with col_s2:
            st.metric("总发油量 (吨)", f"{stats['总发油量(吨)']:.2f}")
        with col_s3:
            st.metric("总损耗 (吨)", f"{stats['总损耗(吨)']:.3f}")
        with col_s4:
            st.metric("合规率", f"{stats['合规率(%)']:.2f}%")

        st.markdown("---")
        st.subheader("📊 按油品统计")
        oil_stats = analyzer.by_oil_type()
        st.dataframe(oil_stats.reset_index(), use_container_width=True)

        st.markdown("---")
        st.subheader("📅 月度发油趋势")
        monthly = analyzer.get_trend_by_month()
        if not monthly.empty:
            st.bar_chart(monthly['发油量'])
            st.caption("每月发油总量（吨）")
        else:
            st.info("暂无按月数据。")

        st.markdown("---")
        st.subheader("⚠️ 异常记录一览")
        abnormal = analyzer.get_abnormal_list()
        if not abnormal.empty:
            st.dataframe(
                abnormal[["交易时间", "油品类型", "核算发油量(吨)", "发油判定", "收油判定"]].head(10),
                use_container_width=True
            )
        else:
            st.success("无异常记录，系统运行良好。")
