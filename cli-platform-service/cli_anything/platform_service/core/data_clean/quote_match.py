"""产品报价核心链路 — quote match.

输入客户表格/编号列表(OE/雷迪克工厂编号/车型) → 列语义识别 →
车型行话翻译为 OE → 生成批量报价模板 → 调用 /productAudit/parse
→ 按 querySource 分流 → 未匹配项三方补查(泰安联/17vin) →
输出 4-sheet Excel(报价结果/待技术员分辨/三方补查待写入/待工厂确认).

不调用 num-save/num-batch-save/param-save/priceAudit — 仅查询与生成
报价单审核任务(系统设计的查询方式)，写后台由后续单独任务处理.
"""

import json
import os
import re

import click

from .cross_validate import _run_excel_script
from .browser_launcher import check_cdp_ready, get_cdp_url
from .oe_query import search_17vin, search_tecalliance
from .cache import get_cached, set_cached


# ── 常量 ──────────────────────────────────────────────

TEMPLATE_HEADERS = ["OE", "通用OE", "名称", "标签车型", "通用车型", "销售等级"]

# querySource 中文说明 (与 backend QuerySource 枚举对应)
QUERY_SOURCE_DESC = {
    0: "未查询到结果",
    1: "OE",
    2: "关联编号(num)",
    3: "关联OE(oem)",
    4: "雷迪克编号(code)",
    5: "模糊匹配",
    6: "原关联编号",
    7: "瓦轴数据匹配",
}

# 精确命中的 querySource 集合 (唯一时归入报价结果)
EXACT_QUERY_SOURCES = {1, 2, 3, 4, 6, 7}

TRANSLATION_TABLE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "..",
    "references", "chinese-vehicle-slang-engine-translation.md",
)

_VEHICLE_PATTERN = re.compile(r'[一-鿿]')
_OE_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9\-/.()]{4,19}$')


# ── 1. load_client_input ──────────────────────────────────────────────

def load_client_input(filepath: str) -> dict:
    """读取客户输入文件 (.xlsx/.xls 或 .txt)，返回统一结构.

    Returns:
        {
            "headers": [...] or None,  # .txt 无表头
            "rows": [{"raw_row": [...], "row_index": int}, ...],
        }
    """
    ext = filepath.rsplit('.', 1)[-1].lower()

    if ext == 'txt':
        rows = []
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append({"raw_row": [line], "row_index": len(rows)})
        return {"headers": None, "rows": rows}

    # .xlsx/.xls — 读取首行作为表头，其余为数据行
    if ext == 'xls':
        script = """
import sys, xlrd, json
wb = xlrd.open_workbook(sys.argv[1])
ws = wb.sheet_by_index(0)
headers = [str(ws.cell_value(0, j)) if ws.cell_value(0, j) != '' else '' for j in range(ws.ncols)]
rows = []
for i in range(1, ws.nrows):
    row = [str(ws.cell_value(i, j)) if ws.cell_value(i, j) != '' else '' for j in range(ws.ncols)]
    if any(row):
        rows.append(row)
print(json.dumps({"headers": headers, "rows": rows}, ensure_ascii=False))
"""
    else:
        script = """
import sys, openpyxl, json
wb = openpyxl.load_workbook(sys.argv[1], data_only=True)
ws = wb.active
all_rows = list(ws.iter_rows(values_only=True))
headers = [str(c) if c is not None else '' for c in all_rows[0]] if all_rows else []
rows = []
for row in all_rows[1:]:
    r = [str(c) if c is not None else '' for c in row]
    if any(r):
        rows.append(r)
print(json.dumps({"headers": headers, "rows": rows}, ensure_ascii=False))
"""

    stdout = _run_excel_script(script, filepath)
    parsed = json.loads(stdout)
    rows = [{"raw_row": r, "row_index": i} for i, r in enumerate(parsed["rows"])]
    return {"headers": parsed["headers"], "rows": rows}


# ── 2. identify_columns ──────────────────────────────────────────────

def identify_columns(rows: list, headers: list = None) -> dict:
    """按内容特征识别 OE列/关联编号列/车型列/名称列/销售等级列.

    不仅看表头 (SKILL.md 规则9) — 按列内容格式特征打分判定.

    Args:
        rows: list of raw_row (list[str])
        headers: 表头列表 or None

    Returns:
        {"oe_col": int|None, "related_col": int|None,
         "vehicle_col": int|None, "name_col": int|None, "grade_col": int|None}
    """
    if not rows:
        return {"oe_col": None, "related_col": None, "vehicle_col": None,
                "name_col": None, "grade_col": None}

    num_cols = max(len(r) for r in rows)
    oe_score = [0] * num_cols
    related_score = [0] * num_cols
    vehicle_score = [0] * num_cols
    name_score = [0] * num_cols
    grade_score = [0] * num_cols

    for row in rows:
        for i in range(num_cols):
            val = row[i].strip() if i < len(row) and row[i] is not None else ""
            if not val:
                continue

            has_comma = ',' in val or '\n' in val or '，' in val
            has_chinese = bool(_VEHICLE_PATTERN.search(val))
            has_digit = bool(re.search(r'\d', val))

            if has_comma:
                related_score[i] += 1
                continue

            if has_chinese:
                if has_digit:
                    vehicle_score[i] += 1
                else:
                    name_score[i] += 1
                continue

            if _OE_PATTERN.match(val):
                oe_score[i] += 1

            if re.match(r'^[A-E]$', val) or re.match(r'^[一二三四五]级$', val):
                grade_score[i] += 1

    # 表头提示 (作为加分项，content 特征优先)
    if headers:
        for i, h in enumerate(headers):
            if i >= num_cols:
                continue
            h = (h or "").strip()
            if '通用' in h and ('oe' in h.lower() or 'OE' in h or '编号' in h):
                related_score[i] += 0.5
            elif h.upper() == 'OE' or '工厂型号' in h or '工厂编号' in h:
                oe_score[i] += 0.5
            elif '车型' in h:
                vehicle_score[i] += 0.5
            elif '名称' in h:
                name_score[i] += 0.5
            elif '等级' in h:
                grade_score[i] += 0.5

    assigned = set()
    result = {}

    for role, scores in (
        ("related_col", related_score),
        ("oe_col", oe_score),
        ("vehicle_col", vehicle_score),
        ("name_col", name_score),
        ("grade_col", grade_score),
    ):
        best_col, best_score = None, 0
        for i, s in enumerate(scores):
            if i in assigned:
                continue
            if s > best_score:
                best_col, best_score = i, s
        if best_col is not None and best_score > 0:
            result[role] = best_col
            assigned.add(best_col)
        else:
            result[role] = None

    return result


# ── 3. translate_vehicle_to_oe ──────────────────────────────────────────

_translation_table_cache = None


def _load_translation_table() -> str:
    """读取车型行话翻译表 (带模块级缓存)."""
    global _translation_table_cache
    if _translation_table_cache is None:
        try:
            with open(TRANSLATION_TABLE_PATH, encoding="utf-8") as f:
                _translation_table_cache = f.read()
        except OSError:
            _translation_table_cache = ""
    return _translation_table_cache


_TABLE_ROW_PATTERN = re.compile(r'^\|(.+)\|$')


def _iter_table_rows(content: str):
    """逐行解析 markdown 表格行 (跳过分隔线/表头行)."""
    for line in content.splitlines():
        line = line.strip()
        m = _TABLE_ROW_PATTERN.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split('|')]
        if not cells:
            continue
        # 跳过分隔线 (|---|---|) 和已知表头行
        if all(re.match(r'^:?-+:?$', c) for c in cells):
            continue
        if cells[0] in ('行话', '品牌'):
            continue
        yield cells


def translate_vehicle_to_oe(vehicle_text: str, deep: bool = False):
    """车型行话翻译为 OE 号.

    先在本地翻译表中做关键词包含匹配; 查不到且 deep=True 时,
    再调用 17vin/泰安联慢路径 (CDP 不可达时优雅降级返回 None).

    Returns:
        OE 号字符串, 或 None (未找到).
    """
    vehicle_text = (vehicle_text or "").strip()
    if not vehicle_text:
        return None

    table = _load_translation_table()
    for cells in _iter_table_rows(table):
        if len(cells) < 3:
            continue
        slang_field = cells[0]
        oe_field = cells[2]

        # 行话字段可能含多个变体, 按常见分隔符拆分
        variants = re.split(r'[/\s]+', slang_field)
        matched = False
        if vehicle_text in slang_field or slang_field in vehicle_text:
            matched = True
        else:
            for v in variants:
                if v and (v in vehicle_text or vehicle_text in v):
                    matched = True
                    break
        if not matched:
            continue

        if not oe_field or oe_field in ('—', '-', ''):
            continue

        first_oe = oe_field.split(',')[0].strip()
        if first_oe and first_oe not in ('—', '-'):
            return first_oe

    if not deep:
        return None

    # deep 慢路径: 17vin / 泰安联 (CDP 不可达或异常时优雅降级)
    cdp_url = get_cdp_url()
    if not check_cdp_ready(cdp_url):
        return None

    try:
        cached = get_cached("vehicle-translate", vehicle_text)
        if cached is not None:
            return cached["value"]

        tec = search_tecalliance(vehicle_text, cdp_url)
        result_oe = None
        if tec:
            for item in tec:
                oes = item.get("oes") or []
                if oes:
                    result_oe = oes[0]
                    break
        if result_oe is None:
            vin = search_17vin(vehicle_text)
            if vin and vin.get("oes"):
                result_oe = vin["oes"][0]

        set_cached("vehicle-translate", vehicle_text, value=result_oe)
        return result_oe
    except Exception:
        return None


# ── 4. build_template_excel ──────────────────────────────────────────

def build_template_excel(rows: list, output_path: str):
    """生成符合批量报价模板的标准 Excel.

    Args:
        rows: list of dict, 每个 dict 包含 TEMPLATE_HEADERS 中的键
        output_path: 输出文件路径
    """
    data = [TEMPLATE_HEADERS] + [
        [str(row.get(h, "")) for h in TEMPLATE_HEADERS] for row in rows
    ]

    script = """
import sys, openpyxl, json
data = json.loads(sys.stdin.read())
wb = openpyxl.Workbook()
ws = wb.active
for row in data:
    ws.append(row)
wb.save(sys.argv[1])
"""
    _run_excel_script(script, output_path, input_data=json.dumps(data, ensure_ascii=False))


# ── 5. submit_and_fetch ──────────────────────────────────────────────

def submit_and_fetch(backend, template_path: str, supplier_range: str = "",
                      query_range: str = "0,1,2,3,4", query_repair_kit: bool = False):
    """上传模板 → 查询新建审核任务 id → 拉取明细行.

    Returns:
        (audit_id, detail_rows)
    """
    filename = os.path.basename(template_path)

    with open(template_path, "rb") as f:
        backend.post(
            "/api/principal/productAudit/parse",
            data={
                "supplierRange": supplier_range,
                "queryRange": query_range,
                "queryRepairKit": "true" if query_repair_kit else "false",
            },
            files={"file": (filename, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )

    list_resp = backend.get(
        "/api/principal/productAudit/list",
        params={"importFileName": filename, "page": 1, "size": 10},
    )
    content = list_resp.get("data", {}).get("content", []) if isinstance(list_resp.get("data"), dict) else []
    if not content:
        raise RuntimeError(f"未找到导入文件 {filename} 对应的审核任务")

    audit = content[0]
    audit_id = audit.get("id")

    detail_resp = backend.get(
        "/api/principal/productAuditData/findAll",
        params={"productAuditId": audit_id},
    )
    detail_data = detail_resp.get("data", [])
    if not isinstance(detail_data, list):
        detail_data = []

    return audit_id, detail_data


# ── 6. classify_results ──────────────────────────────────────────────

def classify_results(detail_rows: list) -> dict:
    """按分流规则对明细行分组.

    - unmatched: querySource == 0
    - to_review: querySource == 5, 或 priceCheckValue 重复出现 (多匹配)
    - matched: querySource in EXACT_QUERY_SOURCES 且 priceCheckValue 唯一

    Returns:
        {"matched": [...], "to_review": [...], "unmatched": [...]}
    """
    counts = {}
    for row in detail_rows:
        pcv = row.get("priceCheckValue")
        counts[pcv] = counts.get(pcv, 0) + 1

    matched, to_review, unmatched = [], [], []

    for row in detail_rows:
        pcv = row.get("priceCheckValue")
        qs = row.get("querySource")

        if qs == 0:
            unmatched.append(row)
        elif qs == 5 or counts.get(pcv, 0) > 1:
            to_review.append(row)
        elif qs in EXACT_QUERY_SOURCES:
            matched.append(row)
        else:
            # 未知 querySource: 归入待技术员分辨, 避免静默丢弃
            to_review.append(row)

    return {"matched": matched, "to_review": to_review, "unmatched": unmatched}


# ── 7. third_party_requery ──────────────────────────────────────────

def third_party_requery(unmatched_rows: list, deep: bool = False, backend=None):
    """对未匹配行进行三方补查 (泰安联/17vin), 命中则二次调用 parse 回查.

    deep=False 或 CDP 不可达或查询异常时, 优雅降级为全部归入 still_unmatched,
    不抛异常.

    Returns:
        (requery_matched, still_unmatched)
    """
    if not unmatched_rows:
        return [], []

    if not deep:
        return [], list(unmatched_rows)

    cdp_url = get_cdp_url()
    if not check_cdp_ready(cdp_url):
        return [], list(unmatched_rows)

    # 逐行查询替换OE/关联编号
    requery_candidates = []  # [(row, new_oe, source)]
    still_unmatched = []

    for row in unmatched_rows:
        pcv = row.get("priceCheckValue", "")
        new_oe, source = None, None
        try:
            cached = get_cached("requery-17vin", pcv)
            if cached is not None:
                vin = cached["value"]
            else:
                vin = search_17vin(pcv)
                set_cached("requery-17vin", pcv, value=vin)

            if vin and vin.get("oes"):
                candidate = vin["oes"][0]
                if candidate and candidate != pcv:
                    new_oe, source = candidate, "17vin"
        except Exception:
            new_oe, source = None, None

        if new_oe:
            requery_candidates.append((row, new_oe, source))
        else:
            still_unmatched.append(row)

    if not requery_candidates or backend is None:
        # 没有候选或没有 backend 可二次调用 parse: 候选行也视为待确认
        still_unmatched.extend(r for r, _, _ in requery_candidates)
        return [], still_unmatched

    # 二次调用 parse 回查
    template_rows = [
        {"OE": new_oe, "通用OE": "", "名称": "", "标签车型": "", "通用车型": "", "销售等级": ""}
        for _, new_oe, _ in requery_candidates
    ]

    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            requery_template = os.path.join(tmpdir, "requery_template.xlsx")
            build_template_excel(template_rows, requery_template)
            _, requery_detail_rows = submit_and_fetch(backend, requery_template)
    except Exception:
        still_unmatched.extend(r for r, _, _ in requery_candidates)
        return [], still_unmatched

    requery_classified = classify_results(requery_detail_rows)
    new_oe_to_candidate = {new_oe: (row, new_oe, source) for row, new_oe, source in requery_candidates}

    requery_matched = []
    for detail_row in requery_classified["matched"]:
        pcv = detail_row.get("priceCheckValue")
        candidate = new_oe_to_candidate.get(pcv)
        if candidate is None:
            continue
        orig_row, new_oe, source = candidate
        enriched = dict(detail_row)
        enriched["new_oe"] = new_oe
        enriched["source"] = source
        enriched["original_input"] = orig_row.get("priceCheckValue", "")
        requery_matched.append(enriched)

    matched_pcvs = {r.get("priceCheckValue") for r in requery_classified["matched"]}
    for orig_row, new_oe, source in requery_candidates:
        if new_oe not in matched_pcvs:
            still_unmatched.append(orig_row)

    return requery_matched, still_unmatched


# ── 8. write_output_excel ──────────────────────────────────────────

_RESULT_FIELDS = ["priceCheckValue", "productId", "name", "code", "querySource",
                  "salePrice", "oemPrice", "suggestPrice", "p1Price", "p2Price",
                  "p3Price", "count"]

_RESULT_HEADERS = ["客户原始输入", "产品ID", "产品名称", "雷迪克编号(code)", "查询方式",
                   "售价", "OEM价格", "建议售价", "P1价格", "P2价格", "P3价格", "库存数", "置信度"]

_CONFIDENCE_BY_QUERY_SOURCE = {
    1: "高", 2: "高", 3: "高", 4: "高", 6: "高", 7: "高",
    5: "低", 0: "无",
}


def _result_row(row: dict, confidence: str = None) -> list:
    qs = row.get("querySource")
    vals = [row.get(f, "") for f in _RESULT_FIELDS[:4]]
    vals.append(QUERY_SOURCE_DESC.get(qs, str(qs)))
    vals.extend(row.get(f, "") for f in _RESULT_FIELDS[5:])
    vals.append(confidence if confidence is not None else _CONFIDENCE_BY_QUERY_SOURCE.get(qs, ""))
    return vals


def write_output_excel(matched: list, to_review: list, requery_matched: list,
                        still_unmatched: list, output_path: str):
    """输出 4-sheet Excel: 报价结果 / 待技术员分辨 / 三方补查待写入 / 待工厂确认.

    - 报价结果: matched 行
    - 待技术员分辨: to_review 行, 同一 priceCheckValue 多行需相邻分组 (附 count 库存数)
    - 三方补查待写入: requery_matched 行, 额外列 新OE/来源/原始输入编号
    - 待工厂确认: still_unmatched 行
    """
    sheets = {}

    # 报价结果
    matched_rows = [_result_row(r) for r in matched]
    sheets["报价结果"] = [_RESULT_HEADERS] + matched_rows

    # 待技术员分辨: 按 priceCheckValue 分组排序, 同组相邻
    sorted_review = sorted(to_review, key=lambda r: str(r.get("priceCheckValue", "")))
    review_rows = [_result_row(r) for r in sorted_review]
    sheets["待技术员分辨"] = [_RESULT_HEADERS] + review_rows

    # 三方补查待写入: 额外列 新OE/来源/原始输入编号
    requery_headers = _RESULT_HEADERS + ["新OE", "来源", "原始输入编号"]
    requery_rows = []
    for r in requery_matched:
        row = _result_row(r, confidence="三方补查")
        row.append(r.get("new_oe", ""))
        row.append(r.get("source", ""))
        row.append(r.get("original_input", ""))
        requery_rows.append(row)
    sheets["三方补查待写入"] = [requery_headers] + requery_rows

    # 待工厂确认
    unmatched_rows = [_result_row(r) for r in still_unmatched]
    sheets["待工厂确认"] = [_RESULT_HEADERS] + unmatched_rows

    script = """
import sys, openpyxl, json
data = json.loads(sys.stdin.read())
wb = openpyxl.Workbook()
first = True
for sheet_name, rows in data.items():
    if first:
        ws = wb.active
        ws.title = sheet_name
        first = False
    else:
        ws = wb.create_sheet(sheet_name)
    for row in rows:
        ws.append(row)
wb.save(sys.argv[1])
"""
    _run_excel_script(script, output_path, input_data=json.dumps(sheets, ensure_ascii=False))


# ── 9. quote match 命令 ──────────────────────────────────────────────

def _row_to_template_dict(raw_row: list, cols: dict) -> dict:
    """根据列识别结果, 将一行客户输入转换为模板字典."""

    def _get(col_key):
        idx = cols.get(col_key)
        if idx is None or idx >= len(raw_row):
            return ""
        return (raw_row[idx] or "").strip()

    return {
        "OE": _get("oe_col"),
        "通用OE": _get("related_col"),
        "名称": _get("name_col"),
        "标签车型": _get("vehicle_col"),
        "通用车型": "",
        "销售等级": _get("grade_col"),
    }


@click.group(name="quote")
def quote():
    """产品报价核心链路 — 输入客户表/编号列表, 输出4-sheet报价Excel."""
    pass


@quote.command(name="match")
@click.option("--file", "input_file", required=True, help="客户输入文件 (.xlsx/.xls/.txt)")
@click.option("--output", default=None, help="输出 Excel 路径 (默认: <输入文件名>_quote_result.xlsx)")
@click.option("--supplier-range", default="", help="商家范围 (companyId, 逗号分隔, 可空)")
@click.option("--query-range", default="0,1,2,3,4", help="关联编号来源范围 (默认 0,1,2,3,4)")
@click.option("--query-repair-kit", is_flag=True, help="查询修理包产品 (默认过滤)")
@click.option("--deep", is_flag=True, help="对未匹配项启用三方补查 (泰安联/17vin, 需 CDP 9250)")
def quote_match(input_file, output, supplier_range, query_range, query_repair_kit, deep):
    """产品报价: 输入OE/工厂编号/车型 → 后台批量报价 → 分流 → 三方补查 → 输出Excel.

    \b
    流程:
      1. 读取客户表格/编号列表, 识别 OE/关联编号/车型/名称/销售等级列
      2. 车型行话翻译为 OE (--deep 时支持 17vin/泰安联慢路径)
      3. 生成标准批量报价模板, 调用 /productAudit/parse 上传
      4. 按 querySource 分流: 报价结果 / 待技术员分辨 / 待工厂确认
      5. --deep 时对未匹配项三方补查, 命中项二次回查后归入"三方补查待写入"
      6. 输出 4-sheet Excel

    不调用 num-save/param-save/priceAudit — 仅生成查询用审核任务,
    写后台由后续单独任务处理.
    """
    from ...platform_service_cli import get_backend

    click.echo(f"读取客户输入: {input_file}", err=True)
    client_input = load_client_input(input_file)
    raw_rows = [r["raw_row"] for r in client_input["rows"]]
    headers = client_input["headers"]

    if not raw_rows:
        click.echo("输入文件无有效数据行", err=True)
        return

    cols = identify_columns(raw_rows, headers)
    click.echo(f"列识别结果: {cols}", err=True)

    template_rows = []
    for raw_row in raw_rows:
        tpl = _row_to_template_dict(raw_row, cols)
        if not tpl["OE"] and tpl["标签车型"]:
            translated = translate_vehicle_to_oe(tpl["标签车型"], deep=deep)
            if translated:
                tpl["OE"] = translated
        if not tpl["OE"]:
            # 无法构造 OE: 跳过该行 (parse 接口只认编号)
            continue
        template_rows.append(tpl)

    if not template_rows:
        click.echo("未能从输入中提取任何 OE/编号，无法提交报价查询", err=True)
        return

    click.echo(f"共 {len(template_rows)} 条待查询编号，生成报价模板...", err=True)

    backend = get_backend()
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        template_path = os.path.join(tmpdir, "quote_template.xlsx")
        build_template_excel(template_rows, template_path)

        click.echo("上传模板并查询批量报价结果...", err=True)
        audit_id, detail_rows = submit_and_fetch(
            backend, template_path, supplier_range, query_range, query_repair_kit,
        )

    click.echo(f"审核任务 id={audit_id}, 共 {len(detail_rows)} 条明细", err=True)

    classified = classify_results(detail_rows)
    click.echo(
        f"分流结果: 报价结果 {len(classified['matched'])} / "
        f"待技术员分辨 {len(classified['to_review'])} / "
        f"未匹配 {len(classified['unmatched'])}",
        err=True,
    )

    if classified["unmatched"]:
        if deep:
            click.echo("对未匹配项进行三方补查 (泰安联/17vin)...", err=True)
        requery_matched, still_unmatched = third_party_requery(
            classified["unmatched"], deep=deep, backend=backend,
        )
        click.echo(
            f"三方补查结果: 命中待写入 {len(requery_matched)} / "
            f"待工厂确认 {len(still_unmatched)}",
            err=True,
        )
    else:
        requery_matched, still_unmatched = [], []

    output_path = output or _default_output_path(input_file)
    write_output_excel(
        classified["matched"], classified["to_review"],
        requery_matched, still_unmatched, output_path,
    )
    click.echo(f"已生成报价结果: {output_path}", err=True)


def _default_output_path(input_file: str) -> str:
    base, _ = os.path.splitext(input_file)
    return f"{base}_quote_result.xlsx"
