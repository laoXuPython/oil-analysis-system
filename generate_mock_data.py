# ============================================================
# generate_mock_data.py —— 按业务规则批量生成模拟历史数据
# 依赖：core.py, data_analysis.py, numpy
# 场景：大油库（4个大罐）→ 小加油站（4个小罐），工作日每天运20吨
# ============================================================

import random
import numpy as np
import csv
import os
from datetime import datetime, timedelta
from core import OilTransaction
from data_analysis import DataManager

# ==================== 1. 节假日判断 ====================
HOLIDAYS_2026 = {
    datetime(2026, 1, 1), datetime(2026, 1, 2), datetime(2026, 1, 3),
    datetime(2026, 1, 29), datetime(2026, 1, 30), datetime(2026, 1, 31),
    datetime(2026, 2, 1), datetime(2026, 2, 2), datetime(2026, 2, 3), datetime(2026, 2, 4),
    datetime(2026, 4, 4), datetime(2026, 4, 5), datetime(2026, 4, 6),
    datetime(2026, 5, 1), datetime(2026, 5, 2), datetime(2026, 5, 3),
    datetime(2026, 6, 19), datetime(2026, 6, 20), datetime(2026, 6, 21),
    datetime(2026, 9, 25), datetime(2026, 9, 26), datetime(2026, 9, 27),
    datetime(2026, 10, 1), datetime(2026, 10, 2), datetime(2026, 10, 3),
    datetime(2026, 10, 4), datetime(2026, 10, 5),
}

def is_workday(date):
    """周一至周五且非法定节假日"""
    if date.weekday() >= 5:
        return False
    if date in HOLIDAYS_2026:
        return False
    return True

# ==================== 2. 油罐初始库存定义 ====================
# 发油方（大油库）：4个大罐，每个1万立方（约7300~8300吨，视密度而定）
# 初始库存随机在3000~6000吨
ISSUE_TANK_STOCK = {
    "柴油1号罐": round(random.uniform(3000, 6000), 1),
    "柴油2号罐": round(random.uniform(3000, 6000), 1),
    "汽油1号罐": round(random.uniform(3000, 6000), 1),
    "汽油2号罐": round(random.uniform(3000, 6000), 1),
}

# 收油方（小加油站）：4个小罐，每个50立方（约37吨柴油/34吨汽油）
# 初始库存随机在5~30吨
RECEIVE_TANK_STOCK = {
    "柴油1号罐": round(random.uniform(5, 30), 1),
    "柴油2号罐": round(random.uniform(5, 30), 1),
    "汽油1号罐": round(random.uniform(5, 30), 1),
    "汽油2号罐": round(random.uniform(5, 30), 1),
}

# 罐容上限（50立方换算为吨，按常用密度近似）
RECEIVE_TANK_CAPACITY = {
    "柴油1号罐": 37.0,
    "柴油2号罐": 37.0,
    "汽油1号罐": 34.0,
    "汽油2号罐": 34.0,
}

# ==================== 3. 库存扣减与增加辅助函数 ====================
def consume_from_issue_tank(oil_type, amount_ton):
    """从发油方对应油品的大罐中扣减库存（优先扣存量多的罐）"""
    matching = sorted(
        [(name, stock) for name, stock in ISSUE_TANK_STOCK.items() if oil_type in name],
        key=lambda x: x[1], reverse=True
    )
    remaining = amount_ton
    for tank_name, stock in matching:
        if remaining <= 0:
            break
        if stock >= remaining:
            ISSUE_TANK_STOCK[tank_name] -= remaining
            remaining = 0
        else:
            remaining -= stock
            ISSUE_TANK_STOCK[tank_name] = 0.0

def add_to_receive_tank(oil_type, amount_ton):
    """向收油方对应油品的小罐中增加库存（优先加存量少的罐，均衡液位）"""
    matching = sorted(
        [(name, stock, RECEIVE_TANK_CAPACITY[name]) for name, stock in RECEIVE_TANK_STOCK.items() if oil_type in name],
        key=lambda x: x[1]  # 按存量升序，优先补液位低的
    )
    remaining = amount_ton
    for tank_name, stock, capacity in matching:
        if remaining <= 0:
            break
        space = capacity - stock
        if space >= remaining:
            RECEIVE_TANK_STOCK[tank_name] += remaining
            remaining = 0
        else:
            RECEIVE_TANK_STOCK[tank_name] = capacity
            remaining -= space

def daily_sale_from_receive_tank():
    """模拟加油站每天零批发出：每个小罐消耗掉一部分，保持库存波动"""
    for tank_name in RECEIVE_TANK_STOCK:
        current = RECEIVE_TANK_STOCK[tank_name]
        capacity = RECEIVE_TANK_CAPACITY[tank_name]
        # 如果库存超过5吨，消耗当天运入量的一部分（模拟日常销售）
        if current > 5:
            sale = round(random.uniform(3, 15), 1)
            RECEIVE_TANK_STOCK[tank_name] = max(5, current - sale)
        # 如果库存低于5吨，保持不动（等明天来油再补充）

# ==================== 4. 罐存快照记录 ====================
def record_tank_snapshot(snapshot_date):
    """记录指定日期的所有罐存快照（发油方+收油方）"""
    file = "tank_snapshot.csv"
    header = ["快照日期", "油罐名称", "所属方", "库存量(吨)"]
    file_exists = os.path.exists(file)
    with open(file, 'a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(header)
        for tank_name, stock in ISSUE_TANK_STOCK.items():
            writer.writerow([snapshot_date.strftime('%Y-%m-%d'), tank_name, "发油方", round(stock, 1)])
        for tank_name, stock in RECEIVE_TANK_STOCK.items():
            writer.writerow([snapshot_date.strftime('%Y-%m-%d'), tank_name, "收油方", round(stock, 1)])

# ==================== 5. 主生成函数 ====================
def generate_demo_data(start_str="2026-03-01", end_str="2026-05-31"):
    """
    按工作日历生成模拟运输数据
    每天：柴油一车、汽油一车，每车约20吨
    每月25日：记录所有罐存快照
    """
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    print(f"开始生成 {start_str} 至 {end_str} 模拟数据...")
    print(f"发油方初始库存：{ISSUE_TANK_STOCK}")
    print(f"收油方初始库存：{RECEIVE_TANK_STOCK}")

    record_count = 0
    current = start
    while current <= end:
        # 每月25号记录罐存快照
        if current.day == 25:
            record_tank_snapshot(current)
            print(f"  📸 {current.strftime('%Y-%m-%d')} 罐存快照已记录")

        # 非工作日跳过
        if not is_workday(current):
            current += timedelta(days=1)
            continue

        # 工作日：先模拟加油站当天的零批销售（消耗小罐库存）
        daily_sale_from_receive_tank()

        # 然后柴油、汽油各发一车
        for oil_type in ["柴油", "汽油"]:
            # 生成实际发出量（20吨±0.2波动）
            issue_mass = round(np.random.normal(20.0, 0.1), 3)
            issue_mass = max(19.8, min(20.2, issue_mass))

            density_20 = 835.0 if oil_type == "柴油" else 745.0
            temp = round(np.random.normal(25.0, 5.0), 1)
            deal = OilTransaction(oil_type, density_20, 0.8)
            full = deal.full_chain_calc(issue_mass=issue_mass)

            # 实际装车量（接近理论装车量，噪声小于允差，多数合规）
            theory_load = full["装车量(吨)"]
            actual_load = round(np.random.normal(theory_load, 0.008), 3)

            # 实际收油量（多数正常，8%短量）
            theory_min_recv = full["最低允收量(吨)"]
            if random.random() < 0.08:
                actual_recv = round(theory_min_recv - random.uniform(0.1, 0.5), 3)
            else:
                actual_recv = round(np.random.normal(theory_min_recv + 0.02, 0.01), 3)

            check = deal.check_actual_vs_theory(issue_mass, actual_load, actual_recv)

            # 更新发油方和收油方库存
            consume_from_issue_tank(oil_type, issue_mass)
            add_to_receive_tank(oil_type, actual_recv)

            # 存入台账
            tid = f"OIL-{current.strftime('%Y%m%d')}-{oil_type[:1]}{record_count+1:03d}"
            ttime = current.strftime('%Y-%m-%d') + " 09:00:00"
            DataManager.save_transaction(
                tid, ttime, oil_type, density_20, temp, 0,
                issue_mass, full["发油损耗(吨)"], full["装车量(吨)"],
                full["运输损耗(吨)"], full["到货量(吨)"], full["收油损耗(吨)"],
                full["最低允收量(吨)"], 0.8,
                actual_load, actual_recv,
                check["发油端判定"], check["收油端判定"]
            )
            record_count += 1

        current += timedelta(days=1)

    print(f"✅ 生成完成：{record_count} 条运输记录")
    print(f"   工作日数：约{record_count//2} 天")
    print(f"   台账文件：{DataManager.CSV_FILE}")
    print(f"   罐存文件：tank_snapshot.csv")

# ==================== 运行入口 ====================
if __name__ == "__main__":
    print("=" * 60)
    print("  🚛 油库→加油站 运输模拟数据生成器")
    print("=" * 60)
    generate_demo_data("2026-03-01", "2026-05-31")
