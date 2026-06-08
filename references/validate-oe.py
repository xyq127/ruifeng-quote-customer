#!/usr/bin/env python3
"""
睿锋智链 Excel 关联编号 OE 校验脚本

用法: python3 validate_oe.py <Excel文件路径>

功能:
  1. 检查每行的"工厂OE"是否存在于"关联编号"列中
  2. 分类不匹配项: DAC格式、格式差异(归一化匹配)、真正缺失
  3. 输出详细报告和统计

依赖: pandas, openpyxl
"""

import sys
import pandas as pd

def validate_oe(file_path):
    df = pd.read_excel(file_path)

    if "工厂OE" not in df.columns:
        print("错误: 文件中未找到'工厂OE'列")
        print(f"可用列: {list(df.columns)}")
        sys.exit(1)

    related_col = "关联编号"
    if related_col not in df.columns:
        print("错误: 文件中未找到'关联编号'列")
        sys.exit(1)

    print(f"=== 数据校验: {file_path} ===")
    print(f"总行数: {len(df)}\n")

    match_count = 0
    mismatch_count = 0
    dac_format = []
    format_diff = []
    truly_missing = []

    for i, row in df.iterrows():
        oe = str(row["工厂OE"]).strip()
        related = str(row[related_col]).strip() if pd.notna(row[related_col]) else ""

        # 原始匹配
        found = oe in related
        if found:
            match_count += 1
            continue

        # DAC格式检测
        is_dac = oe.upper().startswith("DAC")

        # 归一化匹配(去横杠/空格/大小写)
        oe_norm = oe.replace("-", "").replace(" ", "").upper()
        rel_norm = related.replace("-", "").replace(" ", "").upper()
        found_norm = oe_norm in rel_norm

        if is_dac:
            dac_format.append({
                "row": i + 2,
                "id": row.get("编号", ""),
                "oe": oe,
                "vehicle": row.get("标签车型", ""),
            })
            mismatch_count += 1
        elif found_norm:
            # 找出关联编号中的对应值
            parts = [p.strip() for p in related.replace("\n", "\\n").split("\\n")]
            matched = [p for p in parts if p.replace("-", "").replace(" ", "").upper() == oe_norm]
            format_diff.append({
                "row": i + 2,
                "id": row.get("编号", ""),
                "oe": oe,
                "matched": matched[0] if matched else "?",
                "vehicle": row.get("标签车型", ""),
            })
            mismatch_count += 1
        else:
            truly_missing.append({
                "row": i + 2,
                "id": row.get("编号", ""),
                "oe": oe,
                "vehicle": row.get("标签车型", ""),
                "related_preview": related[:80] + "..." if len(related) > 80 else related,
            })
            mismatch_count += 1

    # 输出报告
    print(f"✅ 匹配: {match_count} / {len(df)}")
    print(f"❌ 不匹配: {mismatch_count} / {len(df)}\n")

    if dac_format:
        print(f"--- A. DAC格式轴承型号(非OE号): {len(dac_format)} 行 ---")
        for d in dac_format:
            print(f"  行{d['row']}: ID={d['id']} | 车型={d['vehicle']} | OE={d['oe']}")
        print()

    if format_diff:
        print(f"--- B. 格式差异(归一化匹配): {len(format_diff)} 行 ---")
        for d in format_diff:
            print(f"  行{d['row']}: ID={d['id']} | 车型={d['vehicle']} | {d['oe']} → {d['matched']}")
        print()

    if truly_missing:
        print(f"--- C. 真正缺失OE号: {len(truly_missing)} 行 ---")
        for d in truly_missing:
            print(f"  行{d['row']}: ID={d['id']} | 车型={d['vehicle']} | OE={d['oe']}")
            print(f"    关联编号预览: {d['related_preview']}")
        print()

    # 输出不匹配行号列表
    all_mismatch = [d["row"] for d in dac_format + format_diff + truly_missing]
    print(f"不匹配行号: {all_mismatch}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 validate_oe.py <Excel文件路径>")
        sys.exit(1)
    validate_oe(sys.argv[1])
