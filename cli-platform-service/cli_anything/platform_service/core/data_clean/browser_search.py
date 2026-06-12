"""Browser-based search via CloakBrowser CDP — 泰安联/TecDoc 搜索.

通过 CloakBrowser CDP Server 操作泰安联网页进行搜索.
支持隐身模式、人化交互, 避免触发验证码.
"""

import json
import click
import urllib.parse


# ── URL 配置 ──────────────────────────────────────────

TAIANLIAN_SEARCH_URL = (
    "https://www.tecalliance.cn/cn/search/1?"
    "q={query}&numbersearchinput=1&searchtype=0&status=1"
)

TAIANLIAN_LOGIN_URL = "https://www.tecalliance.cn/cn/login"

# ── 默认 CDP 端点 (CloakBrowser) ─────────────────────

DEFAULT_CDP_URL = "http://127.0.0.1:9250"


def get_cdp_url() -> str:
    """获取 CDP 端点 URL."""
    import os
    return os.environ.get("CLOAKBROWSER_CDP_URL", DEFAULT_CDP_URL)


def check_cdp_ready(cdp_url: str) -> bool:
    """检查 CDP Server 是否可达."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{cdp_url}/json/version")
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def build_taianlian_search_url(query: str) -> str:
    """构建泰安联搜索 URL."""
    encoded = urllib.parse.quote(query)
    return TAIANLIAN_SEARCH_URL.format(query=encoded)


def format_search_result(result: dict) -> dict:
    """标准化搜索结果."""
    return {
        "oe": result.get("oe", ""),
        "brand": result.get("brand", ""),
        "product_name": result.get("name", ""),
        "vehicle": result.get("vehicle", ""),
        "position": result.get("position", ""),
        "params": result.get("params", {}),
        "image_url": result.get("image", ""),
    }


# ── Click commands ────────────────────────────────────

@click.command(name="taianlian-search")
@click.option("--query", required=True, help="搜索关键词 (8位数字/OE号/车型)")
@click.option("--cdp-url", default=None, help=f"CDP 端点 (默认: {DEFAULT_CDP_URL})")
@click.option("--web-search", is_flag=True, help="通过 web_search 搜索而非浏览器")
@click.option("--json", "use_json", is_flag=True, help="JSON 输出")
def taianlian_search(query, cdp_url, web_search, use_json):
    """泰安联 TecDoc 搜索.

    通过 CloakBrowser CDP 或 web_search 查询泰安联网站.
    支持用 8位数字编码 或 OE号 搜索配件.

    \b
    使用前提:
    1. CloakBrowser CDP Server 已运行: docker run -d --name cloak -p 9222:9222 cloakhq/cloakbrowser cloakserve
    2. 用户已在浏览器中登录泰安联 (首次需手动登录, 后续持久化 profile 复用)

    \b
    示例:
      cli-anything-platform-service data-clean taianlian-search --query 42820036
      cli-anything-platform-service data-clean taianlian-search --query MR594979
    """
    search_url = build_taianlian_search_url(query)

    if web_search:
        # 降级方案: 通过 web_search 发起搜索
        click.secho(f"[web_search] 泰安联搜索: {query}", fg='blue')
        click.secho(f"  URL: {search_url}", dim=True)
        click.secho("  请使用 Hermes browser_navigate 导航到此 URL", fg='yellow')
        if use_json:
            click.echo(json.dumps({
                "method": "web_search",
                "query": query,
                "url": search_url,
                "instruction": "Use browser_navigate to open this URL in CDP-connected browser"
            }, indent=2, ensure_ascii=False))
        return

    cdp = cdp_url or get_cdp_url()
    cdp_ready = check_cdp_ready(cdp)
    click.secho(f"[CDP] 泰安联搜索: {query}", fg='blue')
    click.secho(f"  CDP: {cdp}", dim=True)
    if not cdp_ready:
        click.secho(
            f"  CDP Server 不可达 ({cdp})。"
            "请确保 Chrome 调试端口已启动: "
            "chrome --remote-debugging-port=9250 --remote-allow-origins=*",
            fg='red',
        )
    click.secho(f"  URL: {search_url}", dim=True)

    # 提示 Agent 操作步骤
    steps = [
        f"1. browser_navigate: {search_url}",
        "2. browser_snapshot: 获取搜索结果",
        "3. 提取: OE号、品牌、车型、参数、图片",
        "4. browser_vision: 截取产品图片",
    ]

    click.secho("  Agent 操作步骤:", fg='yellow')
    for s in steps:
        click.echo(f"    {s}")

    if use_json:
        click.echo(json.dumps({
            "method": "cdp",
            "cdp_url": cdp,
            "query": query,
            "search_url": search_url,
            "cdp_ready": cdp_ready,
            "agent_steps": steps,
        }, indent=2, ensure_ascii=False))
