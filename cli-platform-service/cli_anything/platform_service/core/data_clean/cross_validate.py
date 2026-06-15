"""OE cross-validation — 关联编号交叉验证.

对 Excel 中的工厂 OE 号与关联编号列表进行批量校验,
输出 A/B/C 三类分类结果.
"""

import json
import os
import sys
import subprocess
import tempfile
import click

from .factory_parser import normalize_oe, is_dac_format


# ── 校验逻辑 ──────────────────────────────────────────

def _run_excel_script(script_content: str, filepath: str,
                      python_path: str = None,
                      input_data: str = None) -> str:
    """安全地执行 Excel 读取脚本，通过命令行参数传递路径避免注入."""
    if python_path is None:
        python_path = sys.executable
    tmpdir = tempfile.gettempdir()
    script_path = os.path.join(tmpdir, f"_xl_script_{os.getpid()}.py")
    with open(script_path, 'w') as f:
        f.write(script_content)
    try:
        result = subprocess.run(
            [python_path, script_path, filepath],
            input=input_data,
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(f"脚本执行失败: {result.stderr}")
        return result.stdout
    finally:
        os.remove(script_path)


def validate_oe_in_related(oe: str, related_numbers: str) -> dict:
    """校验单个产品的 OE 是否存在于关联编号列表中.

    Args:
        oe: 工厂 OE 号 (C列)
        related_numbers: 关联编号列表 (G列), 逗号分隔

    Returns:
        {
            "category": "A" | "B" | "C",
            "category_name": "DAC格式" | "格式差异" | "真正缺失",
            "oe": 原始OE,
            "related": 原始关联编号,
            "match_detail": 详细匹配信息
        }
    """
    if not oe or str(oe).strip() in ('', '0', 'nan'):
        return {"category": "C", "category_name": "工厂OE为空",
                "oe": str(oe), "related": str(related_numbers),
                "match_detail": "OE 列为空或为0"}

    oe_str = str(oe).strip()

    # Category A: DAC 格式轴承编号 (非真实 OE)
    if is_dac_format(oe_str):
        return {"category": "A", "category_name": "DAC轴承编号格式",
                "oe": oe_str, "related": str(related_numbers),
                "match_detail": "OE列填入的是轴承规格编号(DACxxxxx)，非车辆原厂OE号"}

    # Category B/C: 归一化比对
    if not related_numbers or str(related_numbers).strip() in ('', '0', 'nan'):
        return {"category": "C", "category_name": "关联编号为空",
                "oe": oe_str, "related": str(related_numbers),
                "match_detail": "关联编号列(G列)为空，需补充"}

    oe_norm = normalize_oe(oe_str)
    related_str = str(related_numbers).strip()
    related_norm = normalize_oe(related_str)

    # 精确归一化匹配
    if oe_norm in related_norm:
        return {"category": "B", "category_name": "归一化匹配(精确)",
                "oe": oe_str, "related": related_str,
                "match_detail": "忽略横杠/空格/大小写后匹配成功"}

    # 逐个关联编号匹配
    parts = [normalize_oe(p.strip()) for p in related_str.split(',')]
    for p in parts:
        if p and oe_norm == p:
            return {"category": "B", "category_name": "归一化匹配(多值)",
                    "oe": oe_str, "related": related_str,
                    "match_detail": f"与关联编号 '{p}' 匹配"}

    # Category C: 真正缺失
    return {"category": "C", "category_name": "真正缺失",
            "oe": oe_str, "related": related_str,
            "match_detail": "关联编号中找不到匹配的OE号"}


def validate_excel(filepath: str) -> list:
    """读取 Excel 文件并批量校验.

    Returns:
        List of validation results, one per row.
    """
    script = """
import sys, openpyxl, json

wb = openpyxl.load_workbook(sys.argv[1], data_only=True)
ws = wb.active

rows = []
for row in ws.iter_rows(min_row=2, values_only=True):
    if any(c is not None for c in row):
        rows.append([str(c) if c is not None else '' for c in row])

print(json.dumps(rows, ensure_ascii=False))
"""
    stdout = _run_excel_script(script, filepath)
    rows = json.loads(stdout)
    results = []

    for row in rows:
        if len(row) < 7:
            continue
        # B=0工厂编码, C=1工厂型号(OE), G=6关联编号
        factory_code = row[0] if len(row) > 0 else ''
        oe = row[1] if len(row) > 1 else ''
        related = row[6] if len(row) > 6 else ''

        validation = validate_oe_in_related(oe, related)
        validation["factory_code"] = factory_code
        results.append(validation)

    return results


def structural_check(filepath: str) -> list:
    """结构性检查: 工厂编码是否全填, C列是否为车辆OE."""
    script = """
import sys, openpyxl, json

wb = openpyxl.load_workbook(sys.argv[1], data_only=True)
ws = wb.active

issues = []
for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=3):
    if all(c is None for c in row):
        continue
    cells = [str(c) if c is not None else '' for c in row]
    b_code = cells[0] if len(cells) > 0 else ''
    c_oe = cells[1] if len(cells) > 1 else ''
    g_rel = cells[6] if len(cells) > 6 else ''

    if not b_code.strip():
        issues.append({"row": i, "col": "B", "issue": "工厂编码为空", "severity": "error"})
    if c_oe.strip() and ('DAC' in c_oe.upper() or 'DU' in c_oe.upper()):
        issues.append({"row": i, "col": "C", "issue": "C列填入轴承编号格式(DAC/DU), 非车辆OE", "severity": "warn"})
    if not g_rel.strip() or g_rel in ('0', 'None'):
        issues.append({"row": i, "col": "G", "issue": "关联编号为空", "severity": "warn"})

print(json.dumps(issues, ensure_ascii=False))
"""
    try:
        stdout = _run_excel_script(script, filepath)
        return json.loads(stdout)
    except RuntimeError:
        return []


# ── Click command ─────────────────────────────────────

@click.command(name="cross-validate")
@click.option("--file", required=True, help="Excel 文件路径")
@click.option("--check-structure", is_flag=True, help="同时进行结构性检查")
@click.option("--json", "use_json", is_flag=True, help="JSON 输出")
def cross_validate(file, check_structure, use_json):
    """OE 关联编号交叉验证.

    读取 Excel 文件, 校验每行的工厂OE号(C列)
    是否存在于关联编号(G列)中, 输出 A/B/C 三类:
      A = DAC格式(非真实OE)
      B = 归一化匹配(忽略横杠空格)
      C = 真正缺失
    """
    if not file.endswith(('.xlsx', '.xls')):
        click.secho(f"错误: 仅支持 .xlsx/.xls 文件: {file}", fg='red')
        return

    try:
        results = validate_excel(file)
    except Exception as e:
        click.secho(f"校验失败: {e}", fg='red')
        return

    if use_json:
        output = {"results": results}
        if check_structure:
            output["structural_issues"] = structural_check(file)
        click.echo(json.dumps(output, indent=2, ensure_ascii=False))
        return

    # 统计
    cats = {"A": [], "B": [], "C": []}
    for r in results:
        cats[r["category"]].append(r)

    click.secho(f"\n=== 关联编号校验报告 ===", fg='cyan', bold=True)
    click.secho(f"文件: {file}", dim=True)
    click.secho(f"总产品数: {len(results)}", fg='blue')

    click.echo()
    click.secho(f"A 类 (DAC轴承编号格式): {len(cats['A'])} 个", fg='yellow')
    if cats['A']:
        for r in cats['A'][:5]:
            click.echo(f"  OE={r['oe']} → {r['match_detail']}")

    click.secho(f"B 类 (归一化匹配): {len(cats['B'])} 个", fg='green')
    if cats['B']:
        for r in cats['B'][:5]:
            click.echo(f"  OE={r['oe']} → {r['match_detail']}")

    click.secho(f"C 类 (真正缺失): {len(cats['C'])} 个", fg='red')
    if cats['C']:
        for r in cats['C'][:10]:
            click.echo(f"  [{r['factory_code']}] OE={r['oe']} → {r['match_detail']}")
        if len(cats['C']) > 10:
            click.echo(f"  ... 还有 {len(cats['C']) - 10} 个")

    if check_structure:
        issues = structural_check(file)
        if issues:
            click.echo()
            click.secho(f"结构性检查 ({len(issues)} 个问题):", fg='yellow')
            for iss in issues[:20]:
                tag = "ERROR" if iss['severity'] == 'error' else "WARN"
                color = 'red' if iss['severity'] == 'error' else 'yellow'
                click.secho(f"  行{iss['row']} 列{iss['col']}: [{tag}] {iss['issue']}", fg=color)
