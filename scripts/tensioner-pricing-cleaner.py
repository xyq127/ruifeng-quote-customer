#!/usr/bin/env python3
"""
张紧轮/惰轮报价清单清洗脚本模板
修改 SOURCE_PATH 指向实际数据文件后运行。

输入格式：含以下列的Excel/CSV
  商品编号 | 商品名称 | 规格(适用车型) | 数量 | 盖茨(可选)

输出：标准化报价底表（含标准OE号、发动机型号、匹配备注、置信度）
"""
import csv
import os

# ====== 修改这里 ======
SOURCE_PATH = "/path/to/your/pricing-list.xlsx"
OUTPUT_PATH = "/path/to/output/清洗结果.csv"
IS_EXCEL = True  # True=Excel, False=CSV
# =====================

# 知识库：盖茨码 → OE号/发动机映射
GATES_DB = {}  # 详见 references/gates-tensioner-oe-cross-reference.md

# 知识库：行话 → 发动机/OE映射
VEHICLE_DB = {}  # 详见 references/chinese-vehicle-slang-engine-translation.md

def load_data(path, is_excel):
    """加载数据"""
    if is_excel:
        import subprocess, openpyxl
        wb = openpyxl.load_workbook(path)
        ws = wb.active
        rows = []
        for i in range(2, ws.max_row + 1):
            rows.append({
                'prod_code': str(ws.cell(i, 2).value or '').strip(),
                'prod_name': str(ws.cell(i, 3).value or '').strip(),
                'vehicle': str(ws.cell(i, 4).value or '').strip(),
                'qty': ws.cell(i, 5).value,
                'gates': str(ws.cell(i, 6).value or '').strip(),
            })
        return rows
    else:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return list(csv.DictReader(f))

def match_product(row, gates_db, vehicle_db):
    """对单行执行 Condition A/B 匹配"""
    gates = row['gates']
    vehicle = row['vehicle']
    prod_name = row['prod_name']
    
    std_oe = ""
    engine_model = ""
    match_note = ""
    confidence = "Low"
    
    # Condition A: 有盖茨码
    if gates and gates not in ('None', ''):
        if gates in gates_db:
            info = gates_db[gates]
            std_oe = info['oe']
            engine_model = info['engine']
            match_note = f"盖茨{gates}精准匹配"
            confidence = "High" if std_oe else "Medium"
        else:
            match_note = f"盖茨码{gates}未知，需核对"
            confidence = "Low"
    
    # Condition B: 无盖茨码 → 行话解析
    if not confidence.startswith("High"):
        matched = False
        for vkey, vinfo in vehicle_db.items():
            if vkey[:6] in vehicle or vehicle[:6] in vkey:
                std_oe = vinfo.get('oe', '')
                engine_model = vinfo.get('engine', '')
                match_note = f"行话解析：{vinfo.get('note', '')}"
                confidence = "Medium" if std_oe else "Low"
                matched = True
                break
        
        if not matched:
            # 惰轮放宽匹配
            if '惰轮' in prod_name or '过渡轮' in prod_name or '单轮' in prod_name:
                match_note = "惰轮类产品，轴承尺寸匹配即可"
                confidence = "Low"
            else:
                match_note = "需客户提供原厂OE或车架号"
                confidence = "Low"
    
    return std_oe, engine_model, match_note, confidence

def main():
    rows = load_data(SOURCE_PATH, IS_EXCEL)
    
    output = []
    for r in rows:
        oe, engine, note, conf = match_product(r, GATES_DB, VEHICLE_DB)
        output.append({
            '商品编号': r['prod_code'],
            '商品名称': r['prod_name'],
            '适用车型描述': r['vehicle'],
            '数量': r['qty'],
            '盖茨码': r['gates'],
            '标准OE号': oe,
            '发动机型号': engine,
            '匹配备注(给客户)': note,
            '置信度': conf,
        })
    
    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=[
            '商品编号', '商品名称', '适用车型描述', '数量', '盖茨码',
            '标准OE号', '发动机型号', '匹配备注(给客户)', '置信度'
        ])
        w.writeheader()
        w.writerows(output)
    
    high = sum(1 for r in output if r['置信度'] == 'High')
    med = sum(1 for r in output if r['置信度'] == 'Medium')
    low = sum(1 for r in output if r['置信度'] == 'Low')
    print(f"完成！{len(output)}行：High={high} Medium={med} Low={low}")
    print(f"输出文件：{OUTPUT_PATH}")

if __name__ == '__main__':
    main()
