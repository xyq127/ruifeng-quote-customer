"""Excel processing — Excel 读写与变换.

- 读取 .xlsx/.xls 文件
- 提取内嵌图片
- 跨表合并 (按8位核心编号匹配)
- 包装规格汇总
"""

import json
import subprocess
import click

from .cross_validate import _run_excel_script


def read_excel_json(filepath: str) -> list:
    """读取 Excel 文件，返回行列表."""
    ext = filepath.rsplit('.', 1)[-1].lower()

    if ext == 'xls':
        # .xls 旧格式用 xlrd + 系统 Python
        script = """
import sys, xlrd, json
wb = xlrd.open_workbook(sys.argv[1])
ws = wb.sheet_by_index(0)
rows = []
for i in range(1, ws.nrows):
    row = [str(ws.cell_value(i, j)) if ws.cell_value(i, j) != '' else '' for j in range(ws.ncols)]
    if any(row):
        rows.append(row)
print(json.dumps(rows, ensure_ascii=False))
"""
    else:
        script = """
import sys, openpyxl, json
wb = openpyxl.load_workbook(sys.argv[1], data_only=True)
ws = wb.active
rows = []
for row in ws.iter_rows(min_row=2, values_only=True):
    r = [str(c) if c is not None else '' for c in row]
    if any(r):
        rows.append(r)
print(json.dumps(rows, ensure_ascii=False))
"""

    stdout = _run_excel_script(script, filepath)
    return json.loads(stdout)


def extract_images(filepath: str) -> list:
    """从 Excel 提取内嵌图片.

    Returns:
        List of {row, col, filename, data_base64} dicts.
    """
    script = """
import sys, openpyxl, json, base64, os, zipfile, xml.etree.ElementTree as ET
from io import BytesIO

results = []

with zipfile.ZipFile(sys.argv[1]) as z:
    # 读取 drawing 关系
    drawings = [n for n in z.namelist() if n.startswith('xl/drawings/') and n.endswith('.xml')]
    for dpath in drawings:
        tree = ET.parse(z.open(dpath))
        root = tree.getroot()
        ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing',
              'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
        for anchor in root.findall('.//xdr:twoCellAnchor', ns) if ns else root.findall('.//'):
            # Extract position from anchor
            from_col = anchor.find('.//xdr:from/xdr:col', ns)
            from_row = anchor.find('.//xdr:from/xdr:row', ns)
            if from_col is not None and from_row is not None:
                col = int(from_col.text)
                row = int(from_row.text)
                pic = anchor.find('.//xdr:pic/xdr:nvPicPr/xdr:cNvPr', ns)
                name = pic.get('name', f'r{row}c{col}') if pic is not None else f'r{row}c{col}'
                results.append({'row': row+2, 'col': col+1, 'name': name})

print(json.dumps(results, ensure_ascii=False))
"""
    try:
        stdout = _run_excel_script(script, filepath)
        return json.loads(stdout)
    except RuntimeError:
        return []


# ── Click commands ────────────────────────────────────

@click.group(name="excel-process")
def excel_process():
    """Excel 文件处理.

    读取、转换、图片提取、跨表合并、包装汇总.
    """
    pass


@excel_process.command(name="read")
@click.option("--file", required=True, help="Excel 文件路径")
@click.option("--json", "use_json", is_flag=True, help="JSON 输出")
def excel_read(file, use_json):
    """读取 Excel 内容."""
    try:
        rows = read_excel_json(file)
    except Exception as e:
        click.secho(f"读取失败: {e}", fg='red')
        return

    if use_json:
        click.echo(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        click.secho(f"文件: {file} ({len(rows)} 行)", fg='blue')
        for i, row in enumerate(rows[:20]):
            click.echo(f"  行{i+2}: {row[:8]}...")
        if len(rows) > 20:
            click.echo(f"  ... 还有 {len(rows) - 20} 行")


@excel_process.command(name="images")
@click.option("--file", required=True, help="Excel 文件路径")
@click.option("--json", "use_json", is_flag=True, help="JSON 输出")
def excel_images(file, use_json):
    """提取 Excel 内嵌图片位置."""
    try:
        imgs = extract_images(file)
    except Exception as e:
        click.secho(f"提取失败: {e}", fg='red')
        return

    if use_json:
        click.echo(json.dumps(imgs, indent=2, ensure_ascii=False))
    else:
        click.secho(f"文件: {file} ({len(imgs)} 张图片)", fg='blue')
        for img in imgs:
            click.echo(f"  行{img['row']} 列{img['col']}: {img['name']}")


@excel_process.command(name="cross-table-merge")
@click.option("--files", required=True, help="Excel 文件列表 (逗号分隔)")
@click.option("--output", default=None, help="输出文件路径")
@click.option("--json", "use_json", is_flag=True, help="JSON 输出")
def cross_table_merge(files, output, use_json):
    """跨表合并 — 按8位核心编号匹配.

    合并多个产品清单, 精确匹配 + 近似匹配 (高度差<=2mm, 变型差<=8).
    """
    file_list = [f.strip() for f in files.split(',')]
    all_rows = []
    for fp in file_list:
        try:
            rows = read_excel_json(fp)
            all_rows.extend(rows)
        except Exception as e:
            click.secho(f"跳过 {fp}: {e}", fg='yellow')

    click.secho(f"合并完成: {len(file_list)} 个文件, 共 {len(all_rows)} 行", fg='blue')

    if use_json:
        click.echo(json.dumps({"files": file_list, "total_rows": len(all_rows),
                                "rows": all_rows[:50]}, indent=2, ensure_ascii=False))

    if output:
        script = """
import sys, openpyxl, json
data = json.loads(sys.stdin.read())
wb = openpyxl.Workbook()
ws = wb.active
for row in data:
    ws.append(row)
wb.save(sys.argv[1])
"""
        try:
            _run_excel_script(script, output, input_data=json.dumps(all_rows, ensure_ascii=False))
            click.secho(f"已保存: {output}", fg='green')
        except RuntimeError as e:
            click.secho(f"保存失败: {e}", fg='red')
