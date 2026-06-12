"""17vin EPC query — 17vin 电子零件目录查询.

通过 API 或浏览器 CDP 方式查询 17vin EPC,
获取车辆轮毂轴承 OE 号.
"""

import hashlib
import json
import os
import time
import click
import requests

# ── 配置 ──────────────────────────────────────────────

EPC_API = os.environ.get("17VIN_API", "http://api.17vin.com:8080")
# SECURITY: 优先使用环境变量，fallback 仅用于开发环境
EPC_USERNAME = os.environ.get("17VIN_USERNAME", "ruifengzhilian")
# SECURITY: 优先使用环境变量，fallback 仅用于开发环境
EPC_PASSWORD = os.environ.get("17VIN_PASSWORD", "JSD9Wd2")


def generate_token(username: str, password: str, url_params: str = "") -> str:
    """生成 17vin API token (官方算法).

    token = md5(md5(username) + md5(password) + url_params)
    """
    username_md5 = hashlib.md5(username.encode()).hexdigest()
    password_md5 = hashlib.md5(password.encode()).hexdigest()
    token_string = f"{username_md5}{password_md5}{url_params}"
    return hashlib.md5(token_string.encode()).hexdigest()


def search_vehicle(keyword: str) -> list:
    """搜索车辆型号 (/?action=models).

    使用 keyword 作为 series 参数进行过滤查询.

    Returns:
        List of vehicle matches with model_id, brand, series, etc.
    """
    url = f"{EPC_API}/"
    url_params = f"action=models&series={keyword}"
    token = generate_token(EPC_USERNAME, EPC_PASSWORD, url_params)
    params = {
        "action": "models",
        "series": keyword,
        "user": EPC_USERNAME,
        "token": token,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    except requests.RequestException:
        return []


def search_parts_by_oe(oe_number: str) -> list:
    """通过 OE 号搜索配件 (/?action=search_epc, Section 4 4001).

    Note: 长安/铃木/众泰/日产不支持此接口.
    """
    url = f"{EPC_API}/"
    url_params = f"action=search_epc&query_part_number={oe_number}&query_match_type=smart"
    token = generate_token(EPC_USERNAME, EPC_PASSWORD, url_params)
    params = {
        "action": "search_epc",
        "query_part_number": oe_number,
        "query_match_type": "smart",
        "user": EPC_USERNAME,
        "token": token,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    except requests.RequestException:
        return []


def get_epc_catalog(model_id: str, cata_id: str = "0") -> list:
    """获取 EPC 目录结构 (/?action=cataN).

    cata_id=0 使用 action=cata1 (一级目录),
    cata_id=1 使用 action=cata2, 以此类推.
    """
    url = f"{EPC_API}/"
    depth = int(cata_id) + 1 if cata_id.isdigit() else 1
    action = f"cata{depth}"
    url_params = f"action={action}&model_id={model_id}"
    token = generate_token(EPC_USERNAME, EPC_PASSWORD, url_params)
    params = {
        "action": action,
        "model_id": model_id,
        "user": EPC_USERNAME,
        "token": token,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    except requests.RequestException:
        return []


# ── Click commands ────────────────────────────────────

@click.command(name="epc-query")
@click.option("--keyword", help="车型关键词 (如 '长安CS75')")
@click.option("--vin", help="VIN 码 (17位车架号)")  # TODO: VIN 解码功能尚未实现
@click.option("--oe", help="OE 号搜索配件")
@click.option("--model-id", help="已知 model_id, 直接查 EPC 目录")
@click.option("--cata-id", default="0", help="目录ID (0=一级目录)")
@click.option("--json", "use_json", is_flag=True, help="JSON 输出")
def epc_query(keyword, vin, oe, model_id, cata_id, use_json):
    """17vin EPC 查询.

    支持车型搜索、VIN 识别、OE 反查、EPC 目录浏览.
    """
    if oe:
        results = search_parts_by_oe(oe)
        if use_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            click.secho(f"OE '{oe}' 搜索结果 ({len(results)} 条):", fg='cyan')
            for r in results[:10]:
                click.echo(f"  {r}")
        return

    if model_id:
        results = get_epc_catalog(model_id, cata_id)
        if use_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            click.secho(f"EPC 目录 (model={model_id}, cata={cata_id}):", fg='cyan')
            for c in results:
                name = c.get('name', c.get('cataName', ''))
                cid = c.get('id', c.get('cataId', ''))
                has_child = c.get('hasChild', c.get('childCount', 0))
                click.echo(f"  [{cid}] {name} (子目录: {has_child})")
        return

    if keyword:
        results = search_vehicle(keyword)
        if use_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            click.secho(f"车型搜索 '{keyword}' ({len(results)} 条):", fg='cyan')
            for v in results[:20]:
                vid = v.get('modelId', v.get('id', ''))
                brand = v.get('brandName', v.get('brand', ''))
                series = v.get('seriesName', v.get('series', ''))
                year = v.get('year', '')
                click.echo(f"  [{vid}] {brand} {series} ({year})")
        return

    click.secho("请指定 --keyword / --vin / --oe / --model-id 之一", fg='yellow')
