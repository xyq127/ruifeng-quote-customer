"""OE号码一站式查询（泰安联DAC搜索 + 17vin Section 4）.

对一代轴承，DAC 搜索编码格式: {内径}{外径}00{高}
  例: 45x84x45 → 45840045

使用前提:
  1. Chrome CDP 运行在 127.0.0.1:9250
  2. 泰安联网站已登录（首次需手动登录）
  3. 17vin API 凭据在环境变量或 epc.py fallback 中
"""

import json
import re
import time
import click
import requests
from ...platform_service_cli import output
from .factory_parser import classify_match
from .cache import get_cached, set_cached

# ── DAC 编码工具 ─────────────────────────────────────

def dac_encode(d: int, D: int, B: int) -> str:
    """将一代轴承内径/外径/高编码为 TecDoc 搜索关键词.

    格式: {d}{D}00{B}，每位最多两位数字.
    """
    for val, name in [(d, "内径"), (D, "外径"), (B, "高")]:
        if not isinstance(val, int) or val <= 0 or val > 99:
            raise ValueError(f"{name} 必须为 1-99 的整数，收到: {val}")
    return f"{d:02d}{D:02d}00{B:02d}"


def parse_dimension_input(raw: str):
    """解析用户输入的尺寸字符串, 返回 (d, D, B) 或 None.

    支持格式: "45x84x45" "45*84*45" "45 84 45" "45,84,45"
    """
    parts = re.split(r'[xX*,\s]+', raw.strip())
    if len(parts) != 3:
        return None
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def parse_dac_code(raw: str):
    """尝试将输入解析为 DAC 编码, 返回 (d, D, B) 或 None.

    DAC 编码为 8-10 位数字，格式 {d}{D}00{B}.
    例: 45840045 → 45, 84, 45
    """
    s = raw.strip()
    m = re.match(r'^(\d{2})(\d{2})00(\d{2,4})$', s)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


def identify_input(raw: str):
    """判断输入类型并返回结构化数据.

    Returns:
        dict with keys: type, d, D, B, dac_code, oe
    """
    dims = parse_dimension_input(raw)
    if dims:
        d, D, B = dims
        return {"type": "dimension", "d": d, "D": D, "B": B,
                "dac_code": dac_encode(d, D, B)}

    dac = parse_dac_code(raw)
    if dac:
        d, D, B = dac
        return {"type": "dac", "d": d, "D": D, "B": B, "dac_code": raw.strip()}

    return {"type": "oe", "oe": raw.strip()}


# ── 泰安联搜索 ───────────────────────────────────────

def search_tecalliance(query: str, cdp_url: str = "http://127.0.0.1:9250"):
    """泰安联快速搜索 — response 拦截模式（优先），降级文本解析.

    自动启动/复用 Chrome 实例（browser_launcher），无需外部 CDP Server。

    Args:
        query: 搜索关键词 (DAC 编码或 OE 号)
        cdp_url: CDP 端点 URL (保留参数兼容性)

    Returns:
        list of dict: [{brand, oes, source: "tecalliance"}, ...]
        None: 浏览器不可用时降级
    """
    try:
        from .browser_launcher import search_tecalliance_fast, BrowserNotAvailableError
    except ImportError:
        return None

    try:
        return search_tecalliance_fast(query)
    except BrowserNotAvailableError:
        return None


# ── 17vin Section 4 查询 ─────────────────────────────

def search_17vin(oe: str):
    """查询 17vin Section 4 OE 互换号和车型.

    三步: 4001 search_epc → 4004 get_interchange → 40031 get_modellist
    """
    from .epc import generate_token, EPC_API, EPC_USERNAME, EPC_PASSWORD

    result = {"oes": [], "brand_parts": [], "vehicles": []}

    def _call(url_params):
        token = generate_token(EPC_USERNAME, EPC_PASSWORD, url_params)
        full = f"{EPC_API}{url_params}&user={EPC_USERNAME}&token={token}"
        for _ in range(2):
            try:
                r = requests.get(full, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                return r.json()
            except Exception:
                time.sleep(0.5)
        return {"code": -1}

    # Step 1: 4001
    r1 = _call(f"/?action=search_epc&query_part_number={oe}&query_match_type=smart")
    if r1.get("code") != 1 or not r1.get("data"):
        return result
    group_id = r1["data"][0].get("Group_id", "")
    if not group_id:
        return result

    time.sleep(0.3)

    # Step 2: 4004
    r2 = _call(f"/?action=get_interchange_from_part_number_and_group_id_plus_zh"
               f"&part_number={oe}&group_id={group_id}")
    if r2.get("code") == 1:
        ii = r2.get("data", {}).get("InterchangeInfo", {}) or {}
        for item in (ii.get("OeInterchange", []) or []):
            for p in [item.get("Part_number", ""), item.get("Replacement_part_number", "")]:
                if p.strip() and p.strip() != oe:
                    result["oes"].append(p.strip())

        major_brands = {"SKF", "NSK", "FAG", "INA", "NTN", "KOYO", "TIMKEN", "SNR"}
        for item in (ii.get("FactoryInterchange", []) or []):
            brand = item.get("Brand_name_en", "").strip().upper()
            pn = item.get("Part_number", "").strip()
            if brand in major_brands and pn:
                result["brand_parts"].append(f"{item['Brand_name_en']}:{pn}")

    time.sleep(0.3)

    # Step 3: 40031
    r3 = _call(f"/?action=get_modellist_from_part_number_and_group_id"
               f"&part_number={oe}&group_id={group_id}")
    if r3.get("code") == 1:
        models = [m.get("Detail", "") for m in
                  (r3.get("data", {}).get("ModelListStd", []) or []) if m.get("Detail")]
        result["vehicles"] = models[:10]

    return result


# ── Click 命令 ────────────────────────────────────────

@click.command(name="oe-query")
@click.option("--query", "-q", required=True, help="搜索关键词: 尺寸(45x84x45) / DAC编码(45840045) / OE号")
@click.option("--skip-tecalliance", is_flag=True, help="跳过泰安联搜索")
@click.option("--skip-17vin", is_flag=True, help="跳过17vin查询")
@click.option("--cdp-url", default="http://127.0.0.1:9250", help="Chrome CDP 地址")
def oe_query(query, skip_tecalliance, skip_17vin, cdp_url):
    """一站式OE查询: 泰安联DAC搜索 + 17vin OE互换 + 车型验证.

    自动识别输入类型:
    \b
    - 尺寸格式: "45x84x45" → 转为 DAC 编码 45840045 搜索泰安联
    - DAC 编码: "45840045" → 直接搜索泰安联
    - OE 号: "31110-RAA-A01" → 走 17vin section 4 查询互换号和车型
    """
    parsed = identify_input(query)

    if parsed["type"] == "oe":
        oe = parsed["oe"]
        click.echo(f"输入类型: OE号 ({oe})", err=True)
    else:
        dims = f"{parsed['d']}x{parsed['D']}x{parsed['B']}"
        dac = parsed["dac_code"]
        click.echo(f"输入类型: {dims} → DAC 编码: {dac}", err=True)
        oe = dac

    result = {"query": query, "parsed": parsed, "tecalliance": None, "17vin": None}
    from_cache = False

    # 泰安联搜索
    if not skip_tecalliance:
        cached = get_cached("tecalliance", oe)
        if cached is not None:
            tec = cached["value"]
            from_cache = True
            click.echo(f"  泰安联: 缓存命中 ({len(tec or [])} 条记录)", err=True)
        else:
            click.echo("正在搜索泰安联...", err=True)
            tec = search_tecalliance(oe, cdp_url)
            if tec is None:
                click.echo("  泰安联: 需要 Playwright (pip install playwright && playwright install chromium)", err=True)
            elif not tec:
                click.echo("  泰安联: 无结果", err=True)
                set_cached("tecalliance", oe, value=tec)
            else:
                click.echo(f"  泰安联: 找到 {len(tec)} 条记录", err=True)
                set_cached("tecalliance", oe, value=tec)
        result["tecalliance"] = tec or []

    # 17vin 查询
    if not skip_17vin:
        cached = get_cached("17vin", oe)
        if cached is not None:
            vin = cached["value"]
            from_cache = True
            click.echo(f"  17vin: 缓存命中 (OE互换 {len(vin['oes'])}条 / "
                       f"品牌件 {len(vin['brand_parts'])}条 / "
                       f"车型 {len(vin['vehicles'])}条)", err=True)
        else:
            click.echo("正在查询 17vin...", err=True)
            vin = search_17vin(oe)
            if vin["oes"] or vin["brand_parts"] or vin["vehicles"]:
                click.echo(f"  17vin: OE互换 {len(vin['oes'])}条 / "
                           f"品牌件 {len(vin['brand_parts'])}条 / "
                           f"车型 {len(vin['vehicles'])}条", err=True)
            else:
                click.echo("  17vin: 无结果", err=True)
            set_cached("17vin", oe, value=vin)
        result["17vin"] = vin

    # 结构化匹配分类: 根据 tecalliance/17vin 是否有结果 + identify_input 的 type 推断
    tec_result = result["tecalliance"]
    vin_result = result["17vin"]
    has_result = bool(tec_result) or bool(
        vin_result and (vin_result.get("oes") or vin_result.get("brand_parts") or vin_result.get("vehicles"))
    )
    result.update(classify_match(parsed.get("type"), has_result))
    result["from_cache"] = from_cache

    output(result)
