# ============================================================
# data_analysis.py —— 油料台账管理与统计分析（Pandas 增强版）
# 依赖：pandas（pip install pandas）
# 功能：
#   DataManager：        CSV 文件的创建、追加、读取、按条件查询
#   StatisticsAnalyzer： 基于 DataFrame 的统计汇总（groupby / agg）
# 说明：
#   读取后的核心数据结构是 pandas.DataFrame，可直接用于 Streamlit 图表
# ============================================================

import csv
import os
from datetime import datetime
import pandas as pd

# ==================== 1. 数据管理层 ====================
class DataManager:
    """
    台账数据管理：负责 CSV 文件的读写与查询（返回 DataFrame）
    所有方法都是类方法，因为本类不需要存储每个对象的状态，只作为工具类。
    """

    # 类属性：文件名、表头、需要转换为数字的列名
    CSV_FILE = "oil_record.csv"
    HEADER = [
        "交易编号", "交易时间", "油品类型", "标准密度", "实测油温", "发油体积(m³)",
        "核算发油量(吨)", "发油损耗(吨)", "装车吨位(吨)", "运输损耗(吨)",
        "到货吨位(吨)", "收油损耗(吨)", "最低允收吨位(吨)", "内控系数",
        "实际装车吨位", "实际收油吨位", "发油判定", "收油判定"
    ]
    # 哪些列在读取时需要转换成数值（float），避免被当成字符串
    NUMERIC_COLS = [
        "标准密度", "实测油温", "发油体积(m³)", "核算发油量(吨)",
        "发油损耗(吨)", "装车吨位(吨)", "运输损耗(吨)",
        "到货吨位(吨)", "收油损耗(吨)", "最低允收吨位(吨)",
        "内控系数", "实际装车吨位", "实际收油吨位"
    ]

    @classmethod
    def _ensure_file(cls):
        """私有方法：确保 CSV 文件存在，若不存在则创建并写入表头。"""
        if not os.path.exists(cls.CSV_FILE):
            with open(cls.CSV_FILE, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(cls.HEADER)  # 写入表头

    @classmethod
    def save_transaction(cls, transaction_id, transaction_time,
                         oil_type, density_20, temp, issue_vol,
                         issue_mass, issue_loss, loaded_mass, transport_loss,
                         arrived_mass, receive_loss, min_receipt, control_factor,
                         actual_loaded, actual_received, issue_judge, receive_judge):
        """
        将一笔完整的交易记录追加到 CSV 台账中。
        参数顺序与 CSV 表头一一对应，调用前请确保已算好所有数值。
        """
        cls._ensure_file()  # 先保证文件存在
        # 按表头顺序组装一行数据（数值列预先四舍五入保留3位）
        row = [
            transaction_id, transaction_time,
            oil_type, density_20, temp, issue_vol,
            round(issue_mass, 3), round(issue_loss, 3), round(loaded_mass, 3),
            round(transport_loss, 3), round(arrived_mass, 3), round(receive_loss, 3),
            round(min_receipt, 3), control_factor,
            actual_loaded, actual_received,
            issue_judge, receive_judge
        ]
        with open(cls.CSV_FILE, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(row)

    @classmethod
    def load_all(cls):
        """
        读取所有台账记录，返回 pandas DataFrame。
        数值列自动转为 float（无法转换的填 0），确保后续统计不出错。
        """
        cls._ensure_file()
        df = pd.read_csv(cls.CSV_FILE, encoding='utf-8-sig')
        # 将数值列强制转为 float，转换失败的变成 NaN 再填充为 0.0
        for col in cls.NUMERIC_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        return df

    @classmethod
    def query_by_date(cls, start_date, end_date):
        """
        按日期范围查询交易记录，返回 DataFrame。
        start_date, end_date 格式为 'YYYY-MM-DD'，例如 '2026-05-01'
        """
        df = cls.load_all()
        if df.empty:
            return df
        # 从“交易时间”列中提取前10个字符作为日期（假设格式为 '2026-05-01 10:30:00'）
        df['日期'] = df['交易时间'].str[:10]
        # 布尔索引筛选
        mask = (df['日期'] >= start_date) & (df['日期'] <= end_date)
        result = df[mask].drop(columns=['日期'])  # 删除临时添加的日期列再返回
        return result

    @classmethod
    def query_abnormal(cls):
        """查询所有异常记录（发油超损 或 收油短量），返回 DataFrame"""
        df = cls.load_all()
        if df.empty:
            return df
        # str.contains 检查字符串是否包含“超损”或“短量”，na=False 表示遇到NaN不报错
        abnormal_issue = df['发油判定'].str.contains('超损', na=False)
        abnormal_receive = df['收油判定'].str.contains('短量', na=False)
        return df[abnormal_issue | abnormal_receive]


# ==================== 2. 统计汇总层（基于 DataFrame） ====================
class StatisticsAnalyzer:
    """
    统计分析类：基于 pandas DataFrame 进行油料统计。
    使用前需传入 DataManager.load_all() 返回的 DataFrame（或任何符合格式的 df）。
    本类使用实例方法，因为每个分析器可以持有一份不同的数据（例如按日期筛选后的子集）。
    """

    def __init__(self, df):
        """
        :param df: pandas DataFrame，列名必须与 oil_record.csv 一致。
        """
        self.df = df

    # ---- 基础统计 ----
    def get_basic_stats(self):
        """计算总收发量、总损耗、平均损耗率、合规率，返回字典"""
        total_mass = self.df['核算发油量(吨)'].sum()
        total_loss = (self.df['发油损耗(吨)'] +
                      self.df['运输损耗(吨)'] +
                      self.df['收油损耗(吨)']).sum()
        avg_loss_rate = (total_loss / total_mass * 100) if total_mass > 0 else 0.0

        total_count = len(self.df)
        # 异常记录数：发油判定含“超损”或收油判定含“短量”
        abnormal_mask = (self.df['发油判定'].str.contains('超损', na=False) |
                         self.df['收油判定'].str.contains('短量', na=False))
        abnormal_count = abnormal_mask.sum()  # True 的个数
        compliance_rate = ((total_count - abnormal_count) / total_count * 100) if total_count > 0 else 100.0

        return {
            "总记录数": total_count,
            "总发油量(吨)": round(total_mass, 2),
            "总损耗(吨)": round(total_loss, 3),
            "平均损耗率(%)": round(avg_loss_rate, 4),
            "合规率(%)": round(compliance_rate, 2)
        }

    # ---- 按油品统计（groupby + agg 核心） ----
    def by_oil_type(self):
        """
        按油品类型分组统计：作业次数、发油总量、总损耗、异常次数、平均损耗率。
        返回 DataFrame，索引为油品类型。
        """
        # 为了避免修改原 df，先复制一份（也可以不复制，但习惯安全操作）
        df = self.df.copy()
        # 添加新列：总损耗（三阶段损耗之和）
        df['总损耗'] = df['发油损耗(吨)'] + df['运输损耗(吨)'] + df['收油损耗(吨)']
        # 添加新列：是否异常（布尔值）
        df['是否异常'] = (df['发油判定'].str.contains('超损', na=False) |
                          df['收油判定'].str.contains('短量', na=False))

        # groupby 后 agg 聚合：可以同时计算多个统计指标
        result = df.groupby('油品类型').agg(
            作业次数=('交易编号', 'count'),      # 每组的交易笔数
            发油总量=('核算发油量(吨)', 'sum'),   # 总发油量
            总损耗=('总损耗', 'sum'),            # 总损耗
            异常次数=('是否异常', 'sum')         # 异常笔数（布尔求和）
        )
        # 计算平均损耗率（%）
        result['平均损耗率(%)'] = (result['总损耗'] / result['发油总量'] * 100).round(4)
        return result

    # ---- 按日趋势 ----
    def get_trend_by_day(self):
        """按天汇总：发油量、损耗、笔数，返回 DataFrame（日期升序）"""
        df = self.df.copy()
        df['日期'] = df['交易时间'].str[:10]
        df['总损耗'] = df['发油损耗(吨)'] + df['运输损耗(吨)'] + df['收油损耗(吨)']
        daily = df.groupby('日期').agg(
            发油量=('核算发油量(吨)', 'sum'),
            损耗=('总损耗', 'sum'),
            笔数=('交易编号', 'count')
        ).sort_index()  # 按日期排序
        return daily

    # ---- 按月趋势 ----
    def get_trend_by_month(self):
        """按月汇总：发油量、损耗、笔数，返回 DataFrame（月份升序）"""
        df = self.df.copy()
        df['月份'] = df['交易时间'].str[:7]   # '2026-05'
        df['总损耗'] = df['发油损耗(吨)'] + df['运输损耗(吨)'] + df['收油损耗(吨)']
        monthly = df.groupby('月份').agg(
            发油量=('核算发油量(吨)', 'sum'),
            损耗=('总损耗', 'sum'),
            笔数=('交易编号', 'count')
        ).sort_index()
        return monthly

    # ---- 异常汇总 ----
    def get_abnormal_list(self):
        """返回所有异常记录的子集 DataFrame（包含原始所有列）"""
        abnormal_mask = (self.df['发油判定'].str.contains('超损', na=False) |
                         self.df['收油判定'].str.contains('短量', na=False))
        return self.df[abnormal_mask]


# ==================== 演示 ====================
if __name__ == "__main__":
    print("=" * 60)
    print("  📊 油料台账管理与统计分析（Pandas 版）")
    print("=" * 60)

    # 1. 若台账为空，造三条模拟数据（方便演示）
    DataManager._ensure_file()
    df_existing = DataManager.load_all()
    if df_existing.empty:
        print("台账为空，正在写入模拟数据...")
        # 第1笔：柴油，正常
        DataManager.save_transaction(
            "OIL-20260501001", "2026-05-01 10:30:00", "柴油", 835.0, 25.0, 12000,
            9940.0, 9.94, 9930.06, 20.85, 9909.21, 14.86, 9894.35, 0.8,
            9931.0, 9896.0, "合规", "合规"
        )
        # 第2笔：汽油，正常
        DataManager.save_transaction(
            "OIL-20260502001", "2026-05-02 14:00:00", "汽油", 745.0, 30.0, 8000,
            5960.0, 5.96, 5954.04, 12.50, 5941.54, 8.91, 5932.63, 0.8,
            5950.0, 5930.0, "合规", "合规"
        )
        # 第3笔：柴油，收油端异常（短量）
        DataManager.save_transaction(
            "OIL-20260503001", "2026-05-03 09:15:00", "柴油", 835.0, 22.0, 15000,
            12450.0, 12.45, 12437.55, 26.12, 12411.43, 18.62, 12392.81, 0.8,
            12410.0, 12370.0, "合规", "短量"
        )
        print("模拟数据已写入。\n")

    # 2. 读取数据
    df_all = DataManager.load_all()
    print(f"台账共 {len(df_all)} 条记录。\n")

    # 3. 统计分析
    analyzer = StatisticsAnalyzer(df_all)

    print("--- 基础统计 ---")
    for k, v in analyzer.get_basic_stats().items():
        print(f"  {k}：{v}")

    print("\n--- 按油品统计 ---")
    print(analyzer.by_oil_type())

    print("\n--- 每日趋势 ---")
    print(analyzer.get_trend_by_day())

    print("\n--- 每月趋势 ---")
    print(analyzer.get_trend_by_month())

    print("\n--- 异常记录 ---")
    abnormal_df = analyzer.get_abnormal_list()
    if not abnormal_df.empty:
        print(abnormal_df[['交易时间', '油品类型', '核算发油量(吨)', '发油判定', '收油判定']])
    else:
        print("  无异常。")
