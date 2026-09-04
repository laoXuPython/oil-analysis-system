# ============================================================
# 军民融合油料计量与损耗分析系统（核心计算 + 简易日志）
# 功能：
#   1. 根据油品种类、实测体积、温度、标准密度，自动换算标准体积与质量
#   2. 按国标自动分摊发油、运输、收油三方损耗
#   3. 支持设置“管理控制系数”，产生比国标更严格的内部管控上限
#   4. 录入实际装车/收油数据后，自动比对理论值并判定合规/超损/短量
#   5. 每次作业生成一行简易操作日志，保存在 simple_log.txt 中
# ============================================================

import math  # 确保文件顶部已有 import math，没有就加上
import csv
import os
from datetime import datetime

class OilTransaction:
    """油料交易核心类：计量、损耗分摊、验收判定 + 简易操作日志"""

    # ---------- 国标允许损耗率（常量） ----------
    LOSS_RATE_ISSUE = 0.001      # 发油损耗率 0.1%
    LOSS_RATE_TRANSPORT = 0.0021 # 运输损耗率 0.21%
    LOSS_RATE_RECEIVE = 0.0015   # 收油损耗率 0.15%

    # ---------- 油品膨胀系数（用于VCF计算） ----------
    EXPANSION = {
        "汽油": 0.00120,   # 汽油膨胀系数
        "航煤": 0.00100,   # 航煤膨胀系数
        "柴油": 0.00095    # 柴油膨胀系数
    }

    def __init__(self, oil_type, density_20, control_factor=0.8):
        """
        初始化一笔油料交易
        :param oil_type: 油品类型（汽油/航煤/柴油）
        :param density_20: 标准密度（kg/m³）
        :param control_factor: 管理控制系数，默认0.8，即按国标80%从严控制
        """
        self.oil_type = oil_type
        self.density_20 = density_20
        # 根据油品获取膨胀系数，若未匹配则采用默认值0.0011
        self.alpha = self.EXPANSION.get(oil_type, 0.0011)
        self.control_factor = control_factor

    # ========== 核心计量换算 ==========
    def calc_vcf(self, temp):
        """计算体积修正系数 VCF = 1 - α*(t - 20)"""
        return 1 - self.alpha * (temp - 20)

    def gross_to_standard_vol(self, gross_vol, temp):
        """视体积 → 标准体积"""
        return gross_vol * self.calc_vcf(temp)

    def standard_vol_to_mass(self, standard_vol):
        """标准体积 → 质量（吨），采用标准换算公式：质量 = 标准体积 × 标准密度 / 1000"""
        return standard_vol * self.density_20 / 1000

    # ========== 三方损耗分摊 ==========
    def calc_issue(self, issue_mass):
        """计算发油损耗：发油量 × 发油损耗率，得到装车量"""
        loss = issue_mass * self.LOSS_RATE_ISSUE
        return {"出库量(吨)": issue_mass, "发油损耗(吨)": loss, "装车量(吨)": issue_mass - loss}

    def calc_transport(self, loaded_mass):
        """计算运输损耗：装车量 × 运输损耗率，得到到货量"""
        loss = loaded_mass * self.LOSS_RATE_TRANSPORT
        return {"装车量(吨)": loaded_mass, "运输损耗(吨)": loss, "到货量(吨)": loaded_mass - loss}

    def calc_receive(self, arrived_mass):
        """计算收油损耗：到货量 × 收油损耗率，得到最低允收量"""
        loss = arrived_mass * self.LOSS_RATE_RECEIVE
        return {"到货量(吨)": arrived_mass, "收油损耗(吨)": loss, "最低允收量(吨)": arrived_mass - loss}

    # ========== 全流程一键计算 ==========
    def full_chain_calc(self, issue_vol=None, temp=None, issue_mass=None):
        """
        完整业务链计算：优先使用直接给的质量，否则从体积+温度推算质量
        :return: 包含全部中间结果的字典
        """
        result = {}
        # 如果没有直接给质量，就由体积和温度一步步算出发油质量
        if issue_mass is None and issue_vol is not None and temp is not None:
            std_vol = self.gross_to_standard_vol(issue_vol, temp)      # 视体积→标准体积
            issue_mass = self.standard_vol_to_mass(std_vol)            # 标准体积→质量
            result["标准体积(m³)"] = round(std_vol, 2)
            result["计算所得发油量(吨)"] = round(issue_mass, 3)

        # 链式调用三方损耗计算
        step1 = self.calc_issue(issue_mass)
        step2 = self.calc_transport(step1["装车量(吨)"])
        step3 = self.calc_receive(step2["到货量(吨)"])

        # 将各步骤结果合并到一个字典中返回
        result.update(step1)
        result.update(step2)
        result.update(step3)
        return result

    # ========== 管理控制值（内部更严格损耗上限） ==========
    def calc_control_limits(self, issue_mass):
        """
        基于管理控制系数，计算出比国标更严格的内部控制损耗上限
        控制值 = 国标损耗 × 管理控制系数
        """
        chain = self.full_chain_calc(issue_mass=issue_mass)
        return {
            "国标发油损耗(吨)": chain["发油损耗(吨)"],
            "控制发油损耗(吨)": round(chain["发油损耗(吨)"] * self.control_factor, 3),
            "国标运输损耗(吨)": chain["运输损耗(吨)"],
            "控制运输损耗(吨)": round(chain["运输损耗(吨)"] * self.control_factor, 3),
            "国标收油损耗(吨)": chain["收油损耗(吨)"],
            "控制收油损耗(吨)": round(chain["收油损耗(吨)"] * self.control_factor, 3),
            "当前控制系数": self.control_factor
        }

    # ========== 实际验收对比 ==========
    def check_actual_vs_theory(self, issue_mass, actual_loaded_mass, actual_received_mass):
        chain = self.full_chain_calc(issue_mass=issue_mass)
        # 四舍五入到6位小数，消除浮点数抖动
        theory_loaded = round(chain["装车量(吨)"], 6)
        allow_loss_issue = round(chain["发油损耗(吨)"], 6)
        theory_min_receipt = round(chain["最低允收量(吨)"], 6)

        issue_diff = round(theory_loaded - actual_loaded_mass, 6)
        # 关键修复：偏差绝对值在允许损耗的容差范围内（+1e-6）即为合规
        issue_ok = abs(issue_diff) <= allow_loss_issue + 1e-6

        receive_diff = round(actual_received_mass - theory_min_receipt, 6)
        receive_ok = actual_received_mass >= theory_min_receipt - 1e-6

        return {
            "理论应装车(吨)": theory_loaded,
            "实际装车(吨)": actual_loaded_mass,
            "装车偏差(吨)": issue_diff,
            "发油端判定": "合规" if issue_ok else "超损",
            "理论最低允收(吨)": theory_min_receipt,
            "实际收油(吨)": actual_received_mass,
            "收油偏差(吨)": receive_diff,
            "收油端判定": "合规" if receive_ok else "短量"
        }

    # ========== 简易操作日志（口袋本风格） ==========
    def quick_log(self, issue_vol, temp, actual_loaded, actual_received):
        """
        将本次作业的关键结果写成一行简短记录，追加到 simple_log.txt 中
        格式：时间 油品 发油体积/质量 → 装车吨位(判定) → 收油吨位(判定)
        """
        chain = self.full_chain_calc(issue_vol=issue_vol, temp=temp)
        issue_mass = chain["计算所得发油量(吨)"]
        check = self.check_actual_vs_theory(issue_mass, actual_loaded, actual_received)

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = (f"[{now_str}] {self.oil_type} 发油 {issue_vol}m³ / {issue_mass:.1f}t → "
                f"装车 {actual_loaded}t ({check['发油端判定']}) → "
                f"收油 {actual_received}t ({check['收油端判定']})\n")

        with open("simple_log.txt", "a", encoding="utf-8") as f:
            f.write(line)

        print(f"📝 简易日志已记录在 simple_log.txt")


# ==================== 演示运行 ====================
if __name__ == "__main__":
    print("=" * 60)
    print("  🛢️  油料计量系统演示（简易日志版）")
    print("=" * 60)

    # 模拟一次作业的输入参数
    oil_type = "柴油"
    density_20 = 835.0           # 标准密度 (kg/m³)
    issue_vol = 12000            # 发油体积 (m³)
    temp = 28.5                  # 实测油温 (℃)
    control_factor = 0.8         # 管理控制系数 (80%)
    actual_loaded = 9895.0       # 实际装车吨位（模拟）
    actual_received = 9865.0     # 实际收油吨位（模拟）

    # 创建交易对象并执行全流程计算
    deal = OilTransaction(oil_type, density_20, control_factor)
    full = deal.full_chain_calc(issue_vol=issue_vol, temp=temp)
    issue_mass = full["计算所得发油量(吨)"]

    print(f"\n📋 输入：{oil_type}，标密{density_20}，发油{issue_vol}m³，油温{temp}℃")

    # 显示管理控制损耗
    print("\n" + "=" * 40)
    print("📏 管理控制损耗（系数 {:.0%}）".format(control_factor))
    print("=" * 40)
    control = deal.calc_control_limits(issue_mass)
    print(f"  发油：国标 {control['国标发油损耗(吨)']:.3f}t → 控制 ≤{control['控制发油损耗(吨)']:.3f}t")
    print(f"  运输：国标 {control['国标运输损耗(吨)']:.3f}t → 控制 ≤{control['控制运输损耗(吨)']:.3f}t")
    print(f"  收油：国标 {control['国标收油损耗(吨)']:.3f}t → 控制 ≤{control['控制收油损耗(吨)']:.3f}t")

    # 显示实际验收对比结果
    print("\n" + "=" * 40)
    print("📊 实际验收对比")
    print("=" * 40)
    check = deal.check_actual_vs_theory(issue_mass, actual_loaded, actual_received)
    print(f"  发油端：理论装车 {check['理论应装车(吨)']:.3f}t，实际 {check['实际装车(吨)']}t → {check['发油端判定']}")
    print(f"  收油端：理论最低 {check['理论最低允收(吨)']:.3f}t，实际 {check['实际收油(吨)']}t → {check['收油端判定']}")

    # 保存简易日志
    deal.quick_log(issue_vol, temp, actual_loaded, actual_received)

    print("\n✅ 演示完成。请打开 simple_log.txt 查看简易日志。")
