# ============================================================
# query_demo.py —— 油料台账查询演示脚本
# 功能：现场输入查询条件，立刻返回结果
# ============================================================

from data_analysis import DataManager, StatisticsAnalyzer

print("=" * 60)
print("  🔍 油料台账查询演示")
print("=" * 60)

# 1. 先看看台账有多少数据
df_all = DataManager.load_all()
print(f"\n台账共有 {len(df_all)} 条记录。")

# 2. 按日期范围查询
print("\n--- 查询 2026年3月 的全部记录 ---")
march_data = DataManager.query_by_date("2026-03-01", "2026-03-31")
print(f"3月共 {len(march_data)} 条记录：")
if not march_data.empty:
    print(march_data[['交易时间', '油品类型', '核算发油量(吨)', '发油判定', '收油判定']].head(5))

# 3. 查询异常记录
print("\n--- 所有异常记录 ---")
abnormal = DataManager.query_abnormal()
print(f"异常记录共 {len(abnormal)} 条：")
if not abnormal.empty:
    print(abnormal[['交易时间', '油品类型', '核算发油量(吨)', '发油判定', '收油判定']])

# 4. 按油品分类统计
print("\n--- 按油品分类统计 ---")
analyzer = StatisticsAnalyzer(df_all)
print(analyzer.by_oil_type())

# 5. 查询某个月的每日趋势
print("\n--- 2026年4月 每日发油趋势（前10行） ---")
daily = analyzer.get_trend_by_day()
april = daily[daily.index.str.startswith("2026-04")]
print(april.head(10) if not april.empty else "4月暂无数据")

print("\n✅ 查询演示完成。")
