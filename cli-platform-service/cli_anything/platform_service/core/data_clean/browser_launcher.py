"""Browser lifecycle management via Playwright — 自动启动/复用 Chrome 实例.

提供:
- ensure_browser(): 启动或复用 Chrome（持久化 profile，保留登录态）
- get_page(): 获取新页面用于浏览器操作
- check_cdp_ready() / get_cdp_url(): CDP 端点检测（兼容 quote_match.py）
- parse_tecalliance_text(): 泰安联搜索结果文本解析

替代原 CloakBrowser CDP Server 方案，由 Playwright 直接管理浏览器生命周期。
"""

import os
import re
import logging

logger = logging.getLogger(__name__)

# ── 模块级单例 ─────────────────────────────────────────
_playwright = None
_browser = None
_context = None

# ── 默认 CDP 端点 ──────────────────────────────────────
DEFAULT_CDP_URL = "http://127.0.0.1:9250"
DEFAULT_CDP_PORT = 9250


# ── 浏览器 profile 目录 ─────────────────────────────────
def get_user_data_dir() -> str:
    """持久化浏览器 profile 目录，保留泰安联/TecDoc 登录 session."""
    d = os.path.join(os.path.expanduser("~"), ".claude", "browser-data", "ruifeng-chrome")
    os.makedirs(d, exist_ok=True)
    return d


# ── CDP 检测（保留原签名，兼容 quote_match.py）───────────
def check_cdp_ready(cdp_url: str = None) -> bool:
    """检查 CDP Server / Chrome 调试端口是否可达.

    Args:
        cdp_url: CDP 端点 URL，默认从 get_cdp_url() 获取
    """
    if cdp_url is None:
        cdp_url = get_cdp_url()
    try:
        import urllib.request
        req = urllib.request.Request(f"{cdp_url}/json/version")
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def get_cdp_url() -> str:
    """获取 CDP 端点 URL.

    优先读 BROWSER_CDP_URL 环境变量，
    其次读 CLOAKBROWSER_CDP_URL（向后兼容），
    最后 fallback 到默认值.
    """
    return os.environ.get(
        "BROWSER_CDP_URL",
        os.environ.get("CLOAKBROWSER_CDP_URL", DEFAULT_CDP_URL),
    )


# ── 自定义异常 ──────────────────────────────────────────
class BrowserNotAvailableError(Exception):
    """Playwright 未安装或浏览器启动失败."""
    pass


# ── 浏览器生命周期管理 ───────────────────────────────────
def _get_playwright():
    """延迟导入 Playwright sync API."""
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        raise BrowserNotAvailableError(
            "Playwright 未安装。请运行:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )


def ensure_browser(headless: bool = False, cdp_port: int = DEFAULT_CDP_PORT):
    """获取浏览器实例（混合模式）.

    优先连接已有 CDP 端点（Work Buddy / 用户自启 Chrome），
    复用其登录态和 cookie。
    CDP 不可达时自动启动独立 Chrome 实例（持久化 profile）。

    后续调用返回缓存的 browser/context，不重复创建。

    Args:
        headless: 仅对自动启动模式生效
        cdp_port: Chrome DevTools Protocol 端口

    Returns:
        (browser, context) 元组

    Raises:
        BrowserNotAvailableError: Playwright 未安装或所有方式均失败
    """
    global _playwright, _browser, _context

    # 已连接则复用
    if _browser and _browser.is_connected():
        return _browser, _context

    SyncPlaywright = _get_playwright()

    try:
        _playwright = SyncPlaywright().start()
    except Exception as e:
        raise BrowserNotAvailableError(f"Playwright 启动失败: {e}")

    cdp_url = f"http://127.0.0.1:{cdp_port}"

    # ── 优先连接已有 CDP（Work Buddy / 用户自启 Chrome）──
    if check_cdp_ready(cdp_url):
        try:
            _browser = _playwright.chromium.connect_over_cdp(cdp_url)
            _context = _browser.contexts[0] if _browser.contexts else _browser.new_context()
            logger.info("已连接现有 CDP: %s", cdp_url)
            return _browser, _context
        except Exception as e:
            logger.warning("CDP 连接失败 (%s)，回退到自动启动: %s", cdp_url, e)
            # CDP 探测通过但连接失败 → 可能是短暂的，继续尝试自动启动

    # ── 无 CDP → 自动启动独立 Chrome（持久化 profile）──
    user_data_dir = get_user_data_dir()
    try:
        _context = _playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            args=[
                f"--remote-debugging-port={cdp_port}",
                "--remote-allow-origins=*",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            locale="zh-CN",
            timeout=30000,
        )
        _browser = _context.browser
        logger.info("Chrome 已自动启动 (CDP: %s, profile: %s)", cdp_port, user_data_dir)
        return _browser, _context

    except Exception as e:
        # 清理可能的部分初始化
        _browser = None
        _context = None
        if _playwright:
            try:
                _playwright.stop()
            except Exception:
                pass
            _playwright = None
        raise BrowserNotAvailableError(f"浏览器启动失败: {e}")


def get_page():
    """获取一个新页面用于浏览器操作（从缓存的 context 创建）."""
    _, context = ensure_browser()
    return context.new_page()


# ── 登录态检测 ────────────────────────────────────────

TAIANLIAN_LOGIN_URL = "https://www.tecalliance.cn/cn/login"


def check_login_required(page=None) -> bool:
    """检测当前浏览器是否在泰安联登录页.

    通过检查页面 URL 和标题判断是否需要登录。

    Args:
        page: Playwright Page 对象，为 None 时自动获取

    Returns:
        True: 当前在登录页，需要用户登录
        False: 已登录或无法判断
    """
    if page is None:
        try:
            page = get_page()
        except BrowserNotAvailableError:
            return False

    try:
        url = page.url
        title = page.title()
        # 登录页 URL 特征
        if "/login" in url:
            return True
        # 登录页标题特征
        if "登录" in title and "tecalliance" in url.lower():
            return True
        # 页面内容特征（快速文字检测）
        text = page.inner_text("body")[:500]
        if "请登录" in text or "用户登录" in text:
            return True
    except Exception:
        pass

    return False


def wait_for_login(page=None, timeout_seconds: int = 120) -> bool:
    """等待用户完成泰安联登录.

    轮询检测页面是否离开登录页，直到超时。

    Args:
        page: Playwright Page 对象
        timeout_seconds: 最大等待秒数

    Returns:
        True: 登录成功（已离开登录页）
        False: 超时，仍在登录页
    """
    import time

    if page is None:
        try:
            page = get_page()
        except BrowserNotAvailableError:
            return False

    start = time.time()
    while time.time() - start < timeout_seconds:
        if not check_login_required(page):
            return True
        time.sleep(2)

    return False


def shutdown_browser():
    """关闭浏览器并清理资源（用于测试或显式清理）."""
    global _playwright, _browser, _context
    try:
        if _context:
            _context.close()
    except Exception:
        pass
    try:
        if _playwright:
            _playwright.stop()
    except Exception:
        pass
    _playwright = None
    _browser = None
    _context = None


# ── 泰安联搜索结果解析 ───────────────────────────────────
def parse_tecalliance_text(text: str) -> list:
    """解析泰安联搜索页面的 inner_text，提取品牌和 OE 号.

    Args:
        text: page.inner_text("body") 的原始文本

    Returns:
        list of dict: [{brand, oes, source: "tecalliance"}, ...]
    """
    if "搜索结果 0" in text or "总共 0" in text:
        return []

    results = []
    blocks = text.split("\n\n")
    current = {}

    for block in blocks:
        line = block.strip()
        if not line:
            continue

        # 全大写行（长度 > 2，非 "ZH"）识别为品牌行
        if line.isupper() and len(line) > 2 and line not in ("ZH",):
            if current.get("brand"):
                results.append(current)
            current = {"brand": line, "oes": [], "source": "tecalliance"}
            continue

        # 提取 6-15 位数字 OE 号
        oe_match = re.search(r"\b\d{6,15}\b", line)
        if oe_match and current:
            oe = oe_match.group()
            if oe not in current["oes"]:
                current["oes"].append(oe)

    if current.get("brand"):
        results.append(current)

    return results


# ── 搜索（已优化等待时间）─────────────────────────────

def search_tecalliance_fast(query: str) -> list:
    """泰安联搜索 — 已优化等待时间（1s 替代原 3s）.

    TecDoc 是服务端渲染（SSR），无独立 JSON API。
    实测已登录 CDP 环境：导航 ~1s，内容 0.5s 即可就绪。
    等待 1s 是安全和速度的平衡点。

    Args:
        query: 搜索关键词 (DAC编码/OE号)

    Returns:
        list of dict: [{brand, oes, source: "tecalliance"}, ...]
        空列表: 无结果或异常
    """
    search_url = (
        f"https://www.tecalliance.cn/cn/search/1?"
        f"q={query}&numbersearchinput=1&searchtype=0&status=1"
    )

    page = get_page()
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
        # 实测 0.5s 即有内容，1s 保证稳定
        page.wait_for_timeout(1000)
        text = page.inner_text("body")
        return parse_tecalliance_text(text)
    except Exception:
        return []
    finally:
        page.close()
