"""Backend API queries for data cleaning.

Extended product search for data cleaning workflows:
- Search by ENCODE/keyword (correct API params)
- Search by 8-digit core number
- Search by OE number
- Get related numbers and parameters
- Save verified OE numbers and parameters back to backend
"""

import json
import click
from ...platform_service_cli import get_backend, output
from .factory_parser import normalize_oe, parse_factory_number, classify_match


def _search_once(backend, keyword, query_type, page, size, with_details, extra_params=None):
    """执行一次产品库搜索，返回原始响应."""
    params = {
        "page": page,
        "size": size,
        "queryType": query_type,
        "keyword": keyword,
        "queryThird": "true" if with_details else "false",
    }
    if extra_params:
        params.update(extra_params)
    return backend.get("/api/principal/product/list", params=params)


def _extract_content(result):
    """从产品库搜索响应中提取 content 列表."""
    data = result.get("data", {})
    if not isinstance(data, dict):
        return []
    return data.get("content", data.get("records", []))


def _search_with_retry_chain(backend, keyword, query_type="ENCODE", page=1, size=10,
                              with_details=False, **extra_params):
    """带多轮重试链的产品库搜索.

    依次尝试:
      1. 原始 keyword 直接搜索
      2. normalize_oe(keyword) 归一化(去横杠/空格/大写)后搜索
      3. 若 keyword 可解析出一代轴承核心8位编号(core_8digit)，用其搜索

    每轮命中(content 非空)即停止.

    Returns:
        {
            "result": 命中轮次的原始响应 (或最后一轮的响应),
            "content": 命中轮次的 content 列表 (可能为空),
            "attempts": [{"label": str, "keyword": str, "count": int}, ...],
            "matched_attempt": 命中轮次的 label，全部未命中则为 None,
        }
    """
    attempts = []
    last_result = None

    # 第1轮: 原始 keyword
    result = _search_once(backend, keyword, query_type, page, size, with_details, extra_params)
    last_result = result
    content = _extract_content(result)
    attempts.append({"label": "原始keyword", "keyword": keyword, "count": len(content)})
    if content:
        return {"result": result, "content": content, "attempts": attempts, "matched_attempt": "原始keyword"}

    # 第2轮: 归一化 (去横杠/空格/大写)
    normalized = normalize_oe(keyword)
    if normalized and normalized != keyword:
        result = _search_once(backend, normalized, query_type, page, size, with_details, extra_params)
        last_result = result
        content = _extract_content(result)
        attempts.append({"label": "归一化", "keyword": normalized, "count": len(content)})
        if content:
            return {"result": result, "content": content, "attempts": attempts, "matched_attempt": "归一化"}

    # 第3轮: 核心8位 (一代轴承格式)
    parsed = parse_factory_number(keyword)
    core8 = parsed.get("core_8digit")
    if parsed.get("is_parsable") and core8 and core8 not in (keyword, normalized):
        result = _search_once(backend, core8, query_type, page, size, with_details, extra_params)
        last_result = result
        content = _extract_content(result)
        attempts.append({"label": "核心8位", "keyword": core8, "count": len(content)})
        if content:
            return {"result": result, "content": content, "attempts": attempts, "matched_attempt": "核心8位"}

    return {"result": last_result, "content": [], "attempts": attempts, "matched_attempt": None}


def _read_keywords_from_file(path):
    """从文本文件读取关键词列表，每行一个，忽略空行."""
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def _print_search_result(keyword, chain, page, pages_default=1):
    """以人类可读格式打印单个关键词的搜索结果."""
    result = chain["result"]
    content = chain["content"]
    matched_attempt = chain["matched_attempt"]

    if result.get("code") != 200:
        output(result)
        return

    data = result.get("data", {})
    total = data.get("totalElements", len(content))
    pages = data.get("totalPages", pages_default)

    if matched_attempt and matched_attempt != "原始keyword":
        click.secho(f"提示: 通过{matched_attempt}匹配命中", fg='yellow')

    click.secho(f"搜索 '{keyword}' 共 {total} 条结果 (第{page}/{pages}页)", fg='blue')

    for item in content:
        pid = item.get('id', '')
        code = item.get('code', '')
        oe = item.get('oe', '')
        name = item.get('name', '')
        brand = item.get('brand', '')
        car = item.get('car', '')
        cat = item.get('abcCategory', '')
        num = item.get('num', '')

        click.echo(f"  [{pid}] {name} | OE: {oe} | 编码: {code} | "
                   f"品牌: {brand} | 车型: {car} | 等级: {cat}")


@click.command(name="backend-search")
@click.option("--keyword", default=None, help="搜索关键词 (8位数字/OE号/DAC编号/code)")
@click.option("--keywords", default=None, help="多个搜索关键词，逗号分隔")
@click.option("--file", "keywords_file", default=None, help="关键词文件路径，每行一个关键词")
@click.option("--query-type", default="ENCODE", help="查询类型 (默认 ENCODE)")
@click.option("--page", default=1, type=int, help="页码")
@click.option("--size", default=10, type=int, help="每页条数")
@click.option("--with-details", is_flag=True, help="同时获取关联编号和参数详情")
@click.option("--json", "use_json", is_flag=True, help="JSON 输出")
def backend_search(keyword, keywords, keywords_file, query_type, page, size, with_details, use_json):
    """查询睿锋后台产品库.

    使用正确的 API 参数 (queryType=ENCODE + keyword).
    支持 8位纯数字、OE号、DAC编号、产品 code 等搜索.

    若原始关键词搜索为空，自动尝试归一化(去横杠/空格/大写)
    及一代轴承核心8位编号(如适用)进行重试.

    \b
    --keyword、--keywords、--file 三选一:
      --keyword   单个关键词 (默认用法)
      --keywords  多个关键词，逗号分隔
      --file      关键词文件路径，每行一个关键词
    """
    inputs_given = [opt for opt, val in
                    (("--keyword", keyword), ("--keywords", keywords), ("--file", keywords_file))
                    if val is not None]
    if len(inputs_given) > 1:
        raise click.UsageError(f"{' 和 '.join(inputs_given)} 不能同时使用，请只指定一种输入方式")
    if not inputs_given:
        raise click.UsageError("请指定 --keyword、--keywords 或 --file 之一")

    if keyword is not None:
        keyword_list = [keyword]
    elif keywords is not None:
        keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
    else:
        keyword_list = _read_keywords_from_file(keywords_file)

    backend = get_backend()

    if len(keyword_list) == 1 and keyword is not None:
        # 单个关键词模式：保持原有输出格式不变
        kw = keyword_list[0]
        chain = _search_with_retry_chain(backend, kw, query_type, page, size, with_details)
        if use_json:
            output_data = dict(chain["result"]) if isinstance(chain["result"], dict) else {"result": chain["result"]}
            output_data["attempts"] = chain["attempts"]
            output_data["matched_attempt"] = chain["matched_attempt"]
            output_data.update(classify_match(chain["matched_attempt"], None))
            click.echo(json.dumps(output_data, indent=2, ensure_ascii=False))
            return
        _print_search_result(kw, chain, page)
        return

    # 批量模式
    chains = [(kw, _search_with_retry_chain(backend, kw, query_type, page, size, with_details))
              for kw in keyword_list]

    if use_json:
        results = [
            {
                "keyword": kw,
                "content": chain["content"],
                "attempts": chain["attempts"],
                "matched_attempt": chain["matched_attempt"],
                **classify_match(chain["matched_attempt"], None),
            }
            for kw, chain in chains
        ]
        click.echo(json.dumps({"results": results}, indent=2, ensure_ascii=False))
        return

    for kw, chain in chains:
        click.secho(f"=== 关键词: {kw} ===", fg='cyan', bold=True)
        _print_search_result(kw, chain, page)


def _fetch_product_detail(backend, product_id):
    """获取单个产品的关联编号和参数详情，返回 results 字典."""
    results = {}

    # 获取关联编号
    nums_resp = backend.get("/api/principal/productNumDetail/list",
                            params={"productId": product_id})
    if nums_resp.get("code") != 200:
        results["related_numbers_error"] = nums_resp
    else:
        nums_data = nums_resp.get("data", {})
        if isinstance(nums_data, dict):
            nums_list = []
            for v in nums_data.values():
                if isinstance(v, list):
                    nums_list.extend(v)
            results["related_numbers"] = nums_list
        elif isinstance(nums_data, list):
            results["related_numbers"] = nums_data

    # 获取参数
    params_resp = backend.get("/api/principal/productParamDetail/list",
                              params={"productId": product_id})
    if params_resp.get("code") != 200:
        results["parameters_error"] = params_resp
    else:
        params_data = params_resp.get("data", {})
        if isinstance(params_data, dict):
            params_list = []
            for v in params_data.values():
                if isinstance(v, list):
                    params_list.extend(v)
            results["parameters"] = params_list
        elif isinstance(params_data, list):
            results["parameters"] = params_data

    return results


def _print_product_detail(product_id, results):
    """以人类可读格式打印单个产品的详情."""
    click.secho(f"产品 {product_id} 详情:", fg='cyan', bold=True)

    if "related_numbers_error" in results:
        click.secho(f"\n关联编号查询失败: {results['related_numbers_error']}", fg='red')
    else:
        nums = results.get("related_numbers", [])
        click.secho(f"\n关联编号 ({len(nums)}):", fg='blue')
        for n in nums[:20]:
            oe_val = n.get('oe', n.get('num', ''))
            brand_val = n.get('brand', '')
            click.echo(f"  {oe_val} [{brand_val}]")
        if len(nums) > 20:
            click.echo(f"  ... 还有 {len(nums) - 20} 条")

    if "parameters_error" in results:
        click.secho(f"\n参数查询失败: {results['parameters_error']}", fg='red')
        return

    params = results.get("parameters", [])
    click.secho(f"\n参数 ({len(params)}):", fg='blue')
    for p in params[:10]:
        name_p = p.get('paramName', p.get('name', ''))
        value_p = p.get('paramValue', p.get('value', ''))
        click.echo(f"  {name_p}: {value_p}")
    if len(params) > 10:
        click.echo(f"  ... 还有 {len(params) - 10} 项")


@click.command(name="backend-detail")
@click.option("--product-id", default=None, help="产品ID")
@click.option("--product-ids", default=None, help="多个产品ID，逗号分隔")
@click.option("--file", "product_ids_file", default=None, help="产品ID文件路径，每行一个")
@click.option("--json", "use_json", is_flag=True, help="JSON 输出")
def backend_detail(product_id, product_ids, product_ids_file, use_json):
    """获取产品关联编号和参数详情.

    \b
    --product-id、--product-ids、--file 三选一:
      --product-id   单个产品ID (默认用法)
      --product-ids  多个产品ID，逗号分隔
      --file         产品ID文件路径，每行一个
    """
    inputs_given = [opt for opt, val in
                    (("--product-id", product_id), ("--product-ids", product_ids), ("--file", product_ids_file))
                    if val is not None]
    if len(inputs_given) > 1:
        raise click.UsageError(f"{' 和 '.join(inputs_given)} 不能同时使用，请只指定一种输入方式")
    if not inputs_given:
        raise click.UsageError("请指定 --product-id、--product-ids 或 --file 之一")

    if product_id is not None:
        product_id_list = [product_id]
    elif product_ids is not None:
        product_id_list = [p.strip() for p in product_ids.split(',') if p.strip()]
    else:
        product_id_list = _read_keywords_from_file(product_ids_file)

    backend = get_backend()

    if len(product_id_list) == 1 and product_id is not None:
        # 单个产品ID模式：保持原有输出格式不变
        results = _fetch_product_detail(backend, product_id_list[0])
        if use_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            _print_product_detail(product_id_list[0], results)
        return

    # 批量模式
    all_results = {pid: _fetch_product_detail(backend, pid) for pid in product_id_list}

    if use_json:
        click.echo(json.dumps({"results": all_results}, indent=2, ensure_ascii=False))
        return

    for pid, results in all_results.items():
        click.secho(f"=== 关键词: {pid} ===", fg='cyan', bold=True)
        _print_product_detail(pid, results)


# ── 数据回写命令 ──────────────────────────────────────────

@click.command(name="num-save")
@click.option("--product-id", required=True, help="产品ID")
@click.option("--num", required=True, help="关联编号(OE号)，多个用逗号分隔")
@click.option("--maker-name", default="", help="来源说明(如 17vin EPC/泰安联)")
@click.option("--source", "original_source", type=int, default=3,
              help="数据来源: 0=PDE 1=原表 2=瓦轴 3=手动添加(默认) 4=第三方编号")
@click.option("--json", "use_json", is_flag=True, help="JSON 输出")
def num_save(product_id, num, maker_name, original_source, use_json):
    """写入关联编号到后台.

    将验证后的 OE 号以手动添加方式写入产品关联编号表.
    多个 OE 号用逗号分隔，系统自动排查已存在的编号避免重复.

    \b
    示例:
      data-clean num-save --product-id 007844 --num "31110-RAA-A01"
      data-clean num-save --product-id 007844 --num "OE1,OE2,OE3" --maker "17vin EPC"
    """
    backend = get_backend()
    nums = [n.strip() for n in num.split(',') if n.strip()]
    results = []

    for n in nums:
        params = {
            "productId": product_id,
            "num": n,
            "makerName": maker_name,
            "originalSource": original_source,
        }
        result = backend.post("/api/principal/productNumDetail/save", params=params)
        results.append({"num": n, "result": result})

    if use_json:
        click.echo(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        success_count = sum(1 for r in results
                          if r['result'].get('status') or r['result'].get('code') == 200)
        click.secho(f"关联编号写入: {success_count}/{len(results)} 成功", fg='green')
        for r in results:
            status = "✓" if r['result'].get('status') or r['result'].get('code') == 200 else "✗"
            color = 'green' if status == '✓' else 'red'
            click.secho(f"  {status} {r['num']}", fg=color)


@click.command(name="num-batch-save")
@click.option("--product-id", required=True, help="产品ID")
@click.option("--nums", required=True, help="关联编号列表，逗号分隔")
@click.option("--maker-name", default="", help="来源说明")
@click.option("--source", "original_source", type=int, default=3,
              help="数据来源: 0=PDE 1=原表 2=瓦轴 3=手动添加(默认) 4=第三方编号")
@click.option("--json", "use_json", is_flag=True, help="JSON 输出")
def num_batch_save(product_id, nums, maker_name, original_source, use_json):
    """批量写入关联编号 (单次 HTTP 请求).

    与 num-save 功能相同，但通过 saveBatch 接口一次性提交，
    减少网络开销.

    \b
    示例:
      data-clean num-batch-save --product-id 007844 --nums "OE1,OE2,OE3"
    """
    backend = get_backend()
    num_list = [n.strip() for n in nums.split(',') if n.strip()]
    body = [
        {
            "productId": product_id,
            "num": n,
            "makerName": maker_name,
            "originalSource": original_source,
        }
        for n in num_list
    ]
    result = backend.post("/api/principal/productNumDetail/saveBatch", data=body)

    if use_json:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result.get('status') or result.get('code') == 200:
            click.secho(f"批量写入成功: {len(num_list)} 条关联编号", fg='green')
        else:
            click.secho(f"批量写入失败: {result.get('msg', '未知错误')}", fg='red')


@click.command(name="param-save")
@click.option("--product-id", required=True, help="产品ID")
@click.option("--name", required=True, help="参数名 (如 内径/外径/高/安装位置)")
@click.option("--value", required=True, help="参数值")
@click.option("--type", "param_type", default="文本",
              type=click.Choice(["文本", "数字", "布尔"]), help="参数类型 (默认 文本)")
@click.option("--param-id", default="", help="分类参数ID (可选)")
@click.option("--json", "use_json", is_flag=True, help="JSON 输出")
def param_save(product_id, name, value, param_type, param_id, use_json):
    """写入产品参数到后台.

    将验证后的参数（内径/外径/高/安装位置等）写入产品参数表.
    安装位置示例: "前轮", "后轮", "前左", "前右", "后左", "后右".

    \b
    示例:
      data-clean param-save --product-id 007844 --name "内径" --value "39mm"
      data-clean param-save --product-id 007844 --name "安装位置" --value "前轮"
    """
    backend = get_backend()
    params = {
        "productId": product_id,
        "name": name,
        "type": param_type,
        "paramValue": value,
    }
    if param_id:
        params["paramId"] = param_id

    result = backend.post("/api/principal/productParamDetail/save", params=params)

    if use_json:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result.get('status') or result.get('code') == 200:
            click.secho(f"参数写入成功: {name} = {value}", fg='green')
        else:
            click.secho(f"参数写入失败: {result.get('msg', '未知错误')}", fg='red')
