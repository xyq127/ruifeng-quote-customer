"""Browser-based search — 泰安联/TecDoc 搜索.

通过 Playwright 自动启动/复用 Chrome 实例，直接执行泰安联网页搜索。
无需外部 CDP Server，首次使用时自动启动独立 Chrome。
"""

import json
import click
import urllib.parse

# ── 从 browser_launcher re-export（兼容 quote_match.py 等外部导入）───
from .browser_launcher import (  # noqa: F401 — re-export
    check_cdp_ready,
    get_cdp_url,
    BrowserNotAvailableError,
    parse_tecalliance_text,
    check_login_required,
    wait_for_login,
    search_tecalliance_fast,
    TAIANLIAN_LOGIN_URL,
)


# ── URL 配置 ──────────────────────────────────────────

TAIANLIAN_SEARCH_URL = (
    "https://www.tecalliance.cn/cn/search/1?"
    "q={query}&numbersearchinput=1&searchtype=0&status=1"
)

TAIANLIAN_LOGIN_URL = "https://www.tecalliance.cn/cn/login"


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


# ── 泰安联搜索（直接执行）──────────────────────────────

def _search_tecalliance_direct(query: str) -> list:
    """泰安联快速搜索 — response 拦截 + 登录检测.

    自动检测登录态，未登录时引导用户完成登录。
    优先使用 API 拦截模式获取结构化数据，失败时降级文本解析。

    Returns:
        list of dict: [{brand, oes, source: "tecalliance"}, ...]
    """
    from .browser_launcher import (
        get_page, check_login_required, wait_for_login,
        search_tecalliance_fast,
    )

    page = get_page()
    url = build_taianlian_search_url(query)

    try:
        # 先导航检查登录态
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)

        if check_login_required(page):
            click.secho("", err=True)
            click.secho("  ⚠ 检测到泰安联登录页，需要登录后才能搜索", fg="yellow", err=True)
            click.secho("  请在浏览器窗口中完成登录:", err=True)
            click.secho(f"    登录地址: {TAIANLIAN_LOGIN_URL}", err=True)
            click.secho("  登录成功后 Agent 将自动继续...", fg="blue", err=True)

            if wait_for_login(page, timeout_seconds=120):
                click.secho("  ✓ 登录成功，继续搜索...", fg="green", err=True)
            else:
                click.secho("  ✗ 登录超时，请手动登录后重试", fg="red", err=True)
                return []
    except Exception:
        pass
    finally:
        page.close()

    # 登录确认后，用快速搜索
    try:
        return search_tecalliance_fast(query)
    except Exception:
        return []


# ── Click commands ────────────────────────────────────

@click.command(name="taianlian-search")
@click.option("--query", required=True, help="搜索关键词 (8位数字/OE号/车型)")
@click.option("--cdp-url", default=None, help="CDP 端点 (默认: http://127.0.0.1:9250)")
@click.option("--web-search", is_flag=True, help="通过 web_search 搜索而非浏览器（降级方案）")
@click.option("--json", "use_json", is_flag=True, help="JSON 输出")
def taianlian_search(query, cdp_url, web_search, use_json):
    """泰安联 TecDoc 搜索.

    通过 Playwright 管理的 Chrome 实例自动搜索泰安联网站。
    支持用 8位数字编码 或 OE号 搜索配件。
    首次使用时自动启动独立 Chrome 窗口（持久化登录态）。

    \b
    使用前提:
    1. Playwright 已安装: pip install playwright && playwright install chromium
    2. 首次使用时需在自动打开的 Chrome 窗口中手动登录泰安联 (后续自动复用)

    \b
    示例:
      cli-anything-platform-service data-clean taianlian-search --query 42820036
      cli-anything-platform-service data-clean taianlian-search --query MR594979
    """
    search_url = build_taianlian_search_url(query)

    if web_search:
        # 降级方案: 通过 web_search 发起搜索（无需浏览器）
        click.secho(f"[web_search] 泰安联搜索: {query}", fg="blue")
        click.secho(f"  URL: {search_url}", dim=True)
        click.secho("  请使用 Hermes browser_navigate 导航到此 URL", fg="yellow")
        if use_json:
            click.echo(json.dumps({
                "method": "web_search",
                "query": query,
                "url": search_url,
                "instruction": "Use browser_navigate to open this URL in CDP-connected browser",
            }, indent=2, ensure_ascii=False))
        return

    # ── 直接执行浏览器搜索 ──
    cdp = cdp_url or get_cdp_url()
    click.secho(f"[Browser] 泰安联搜索: {query}", fg="blue")
    click.secho(f"  CDP: {cdp}", dim=True)
    click.secho(f"  URL: {search_url}", dim=True)

    if not check_cdp_ready(cdp):
        # CDP 不可达 → 尝试自动启动 Chrome
        click.secho("  正在启动 Chrome 实例...", fg="yellow")
        try:
            from .browser_launcher import ensure_browser
            ensure_browser(headless=False)
            click.secho("  Chrome 已启动 ✓", fg="green")
        except BrowserNotAvailableError as e:
            click.secho(f"  浏览器不可用: {e}", fg="red")
            if use_json:
                click.echo(json.dumps({
                    "error": "browser_not_available",
                    "message": str(e),
                }, indent=2, ensure_ascii=False))
            return

    try:
        results = _search_tecalliance_direct(query)
    except BrowserNotAvailableError as e:
        click.secho(f"  搜索失败: {e}", fg="red")
        if use_json:
            click.echo(json.dumps({
                "error": "browser_not_available",
                "message": str(e),
            }, indent=2, ensure_ascii=False))
        return

    # ── 输出结果 ──
    if not results:
        click.secho("  无搜索结果", fg="yellow")
        if use_json:
            click.echo(json.dumps({"results": [], "query": query}, ensure_ascii=False))
        return

    click.secho(f"  找到 {len(results)} 个品牌/供应商", fg="green")
    for r in results:
        click.secho(f"    {r['brand']}: {', '.join(r['oes'][:5])}"
                     + (f" (+{len(r['oes']) - 5})" if len(r['oes']) > 5 else ""))

    if use_json:
        click.echo(json.dumps({
            "method": "browser",
            "query": query,
            "search_url": search_url,
            "results": results,
        }, indent=2, ensure_ascii=False))
