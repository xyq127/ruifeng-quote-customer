#!/usr/bin/env python3
"""
17vin EPC CDP 导航脚本 — 通过 Chrome CDP 浏览器自动导航 EPC 目录树，
按车型查找指定配件的 OE/零件号。

用法:
  python3 17vin_epc_cdp_navigator.py --brand 现代 --series 瑞纳 --part 前轮毂轴承
  python3 17vin_epc_cdp_navigator.py --brand 丰田 --series 威驰 --part 前轮毂轴承 --year 2010
  python3 17vin_epc_cdp_navigator.py --brand 本田 --series 飞度 --cata1 底盘 --cata2 前桥

依赖: websocket-client
"""

import websocket, json, time, urllib.request, argparse, sys, re

# ============================================================
# 配置
# ============================================================
CDP_HOST = "http://localhost:9250"
DEFAULT_CATA1_KEYWORDS = ["底盘", "CHASSIS", "前桥", "FRONT AXLE", "前悬", "FRONT SUSP"]
DEFAULT_CATA2_KEYWORDS = ["前桥", "FRONT AXLE", "前轮", "FRONT WHEEL", "前悬", "前转向节"]
DEFAULT_PART_KEYWORDS = ["轮毂轴承", "前轮毂轴承", "车轮轴承", "BEARING", "HUB BEARING", "WHEEL BEARING"]

# ============================================================
# CDP 工具函数
# ============================================================
class CDPClient:
    def __init__(self, host=CDP_HOST, tab_keyword="17vin"):
        self.host = host
        self.ws = None
        self._mid = 0
        self._connect(tab_keyword)

    def _connect(self, tab_keyword):
        pages = json.loads(urllib.request.urlopen(f"{self.host}/json/list").read())
        matches = [p for p in pages if tab_keyword in p.get("url", "")]
        if not matches:
            raise RuntimeError(f"No tab found with keyword '{tab_keyword}'")
        ws_url = matches[0]["webSocketDebuggerUrl"]
        print(f"[CDP] Connected: {matches[0]['title'][:60]}")
        self.ws = websocket.create_connection(ws_url, timeout=15,
                                               http_proxy_host="", http_proxy_port=None)
        self.send("Page.enable")
        time.sleep(0.3)

    def send(self, method, params=None):
        self._mid += 1
        self.ws.send(json.dumps({"id": self._mid, "method": method,
                                  "params": params or {}}))

    def eval_js(self, expr, timeout=10):
        self._mid += 1
        self.ws.send(json.dumps({"id": self._mid, "method": "Runtime.evaluate",
                                  "params": {"expression": expr, "returnByValue": True}}))
        self.ws.settimeout(timeout)
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                msg = json.loads(self.ws.recv())
                if msg.get("id") == self._mid:
                    v = msg.get("result", {}).get("result", {}).get("value")
                    return v
            except:
                break
        return None

    def navigate(self, url, wait=5):
        print(f"[NAV] {url[:100]}...")
        self.send("Page.navigate", {"url": url})
        # Wait for load
        self.ws.settimeout(wait + 3)
        t0 = time.time()
        while time.time() - t0 < wait + 3:
            try:
                msg = json.loads(self.ws.recv())
                if msg.get("method") == "Page.loadEventFired":
                    break
            except:
                break
        time.sleep(wait)
        return self.eval_js("window.location.href")

    def click_text(self, text, tag=None):
        """点击页面中包含指定文本的元素"""
        tag_filter = f" && el.tagName === '{tag}'" if tag else ""
        result = self.eval_js(f"""
(function(){{
    let all = document.querySelectorAll('a, span, div, li, button');
    for(let el of all) {{
        if(el.textContent.trim() === '{text}' && el.offsetParent !== null{tag_filter}) {{
            el.click();
            return 'clicked ' + el.tagName + ': ' + (el.href||'').substring(0,100);
        }}
    }}
    return 'not found';
}})()
""")
        print(f"[CLICK] '{text}' → {result}")
        time.sleep(4)
        return result

    def click_contains(self, text):
        """点击包含指定文本的第一个可见链接"""
        result = self.eval_js(f"""
(function(){{
    let all = document.querySelectorAll('a');
    for(let el of all) {{
        if(el.textContent.includes('{text}') && el.offsetParent !== null) {{
            el.click();
            return 'clicked: ' + el.href.substring(0,120);
        }}
    }}
    return 'not found';
}})()
""")
        print(f"[CLICK] contains '{text}' → {result}")
        time.sleep(4)
        return result

    def get_text(self):
        return self.eval_js("document.body.innerText.substring(0,10000)") or ""

    def get_links(self, href_pattern=None):
        filter_js = f" && a.href.includes('{href_pattern}')" if href_pattern else ""
        return self.eval_js(f"""
(function(){{
    let all = document.querySelectorAll('a');
    let found = [];
    for(let a of all) {{
        if(a.offsetParent !== null{filter_js}) {{
            found.push({{text: a.textContent.trim().substring(0,40), href: a.href}});
        }}
    }}
    return found;
}})()
""") or []

    def close(self):
        if self.ws:
            self.ws.close()


# ============================================================
# EPC 导航步骤
# ============================================================
def step_go_homepage(cdp):
    """导航到 17vin 首页，点击'车型查询'标签"""
    cdp.navigate("https://www.17vin.com/", wait=4)
    cdp.click_text("车型查询")
    time.sleep(2)

def step_select_brand(cdp, brand):
    """点击品牌"""
    cdp.click_text(brand)

def step_select_series(cdp, series):
    """点击车系（需在车系列表页）"""
    # 尝试精确匹配
    result = cdp.click_text(series)
    if "not found" in str(result):
        # 尝试模糊匹配
        result = cdp.click_contains(series)
    return result

def step_select_model(cdp, year=None, engine=None):
    """在车型列表中点击第一个有'配件目录查看>>'的车型"""
    time.sleep(2)
    links = cdp.get_links(href_pattern="cata1")
    if not links:
        # 重试一次
        time.sleep(3)
        links = cdp.get_links(href_pattern="cata1")

    if not links:
        print("[WARN] No cata1 EPC links found on page")
        # 打印页面片段帮助调试
        text = cdp.get_text()
        print(f"[DEBUG] Page text sample: {text[:500]}")
        return None

    # 优先选指定年份
    target = None
    for link in links:
        if "配件目录查看" in link.get("text", ""):
            href = link.get("href", "")
            if year and year in href:
                target = href
                break
            if not target:
                target = href

    if target:
        cdp.navigate(target, wait=6)
        return target
    return None

def step_find_cata1(cdp, keywords=DEFAULT_CATA1_KEYWORDS):
    """在一级目录中找到底盘(CHASSIS)项，点击详情进入二级目录"""
    time.sleep(3)

    # 用 JS 直接点击：找到 cata2 链接的"详情"按钮
    # 底盘 section = 2，URL 模式为 .../2.html
    result = cdp.eval_js("""
(function(){
    let all = document.querySelectorAll('a');
    // 优先找 href 包含 /2.html cata2 的"详情"链接
    for(let a of all) {
        let t = a.textContent.trim();
        let h = a.href || '';
        if(t === '详情' && h.includes('cata2') && /\\/2\\.html/.test(h)) {
            a.click();
            return 'clicked cata2/2.html: ' + h.substring(0,120);
        }
    }
    // 回退：找任何 cata2 的详情链接
    for(let a of all) {
        let t = a.textContent.trim();
        if(t === '详情' && (a.href||'').includes('cata2')) {
            a.click();
            return 'clicked any cata2: ' + a.href.substring(0,120);
        }
    }
    // 最后：找 "2 CHASSIS" 或 "2 底盘" 行的详情
    for(let a of all) {
        if((a.textContent.includes('2') && a.textContent.includes('CHASSIS')) ||
           (a.textContent.includes('2') && a.textContent.includes('底盘'))) {
            a.click();
            return 'clicked chassis text: ' + (a.href||'').substring(0,120);
        }
    }
    return 'not found. visible links with cata2: ' +
        Array.from(document.querySelectorAll('a[href*="cata2"]')).map(a=>a.href.substring(0,80)).join(' | ');
})()
""")
    print(f"[CATA1] JS click: {result}")
    if "clicked" in str(result):
        time.sleep(6)
        return True
    return False

def step_find_cata2(cdp, keywords=DEFAULT_CATA2_KEYWORDS):
    """在二级目录中找到前桥/前轮相关项，点击进入零件列表"""
    time.sleep(3)

    # 用 JS 点击 — 前桥的 partlist 链接通常包含 50_517 或 FRONT AXLE
    result = cdp.eval_js("""
(function(){
    let all = document.querySelectorAll('a');
    // 优先：找包含"前桥"或"FRONT AXLE"文本的链接，点同一行的"详情"
    let targetRow = null;
    for(let a of all) {
        if((a.textContent.includes('前桥') || a.textContent.includes('FRONT AXLE')) && a.href) {
            targetRow = a;
            // 直接点它试试
            a.click();
            return 'clicked front axle text: ' + a.href.substring(0,100);
        }
    }
    // 回退：找 50_517 相关的 partlist 详情链接
    for(let a of all) {
        if(a.textContent.trim() === '详情' && (a.href||'').includes('50_517')) {
            a.click();
            return 'clicked 50_517 detail: ' + a.href.substring(0,100);
        }
    }
    // 最后：找任何 partlist 详情链接
    for(let a of all) {
        if(a.textContent.trim() === '详情' && (a.href||'').includes('partlist')) {
            a.click();
            return 'clicked any partlist: ' + a.href.substring(0,100);
        }
    }
    return 'not found. partlist links: ' +
        Array.from(document.querySelectorAll('a[href*="partlist"]')).map(a=>(a.textContent.trim().substring(0,20)+':'+a.href.substring(0,60))).join(' | ');
})()
""")
    print(f"[CATA2] JS click: {result}")
    if "clicked" in str(result):
        time.sleep(6)
        return True
    return False

def step_extract_parts(cdp, keywords=DEFAULT_PART_KEYWORDS):
    """从零件列表 HTML 表格中提取目标配件的 OE 号"""
    time.sleep(2)

    # 用 DOM 查询直接解析表格
    result = cdp.eval_js(f"""
(function(){{
    let keywords = {json.dumps([kw.lower() for kw in keywords])};
    let rows = document.querySelectorAll('tr');
    let found = [];

    for(let i = 0; i < rows.length; i++) {{
        let cells = rows[i].querySelectorAll('td');
        let rowText = rows[i].textContent || '';

        // 检查是否包含目标关键词
        let matched = keywords.some(kw => rowText.toLowerCase().includes(kw));
        if(!matched) continue;

        // 提取零件号：通常是 td 中第二个单元格的内容
        // 格式: 图号 | 零件号 | 零件名称 | 数量 | ...
        if(cells.length >= 2) {{
            let partNo = cells[1].textContent.trim();
            if(partNo && partNo.length >= 5 && !partNo.includes('零件号')) {{
                found.push({{
                    part_number: partNo,
                    name: cells.length >= 3 ? cells[2].textContent.trim() : '',
                    description: rowText.replace(/\\s+/g, ' ').substring(0,150),
                    source: '17vin_epc_cdp'
                }});
            }}
        }}
    }}
    return found;
}})()
""")
    if result:
        for r in result:
            r["part_number"] = r["part_number"].replace("复制成功", "").strip()
        return result

    # 回退：文本解析
    text = cdp.get_text()
    lines = text.split("\n")
    parts = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        matched = any(kw.lower() in line.lower() for kw in keywords)
        if matched and line:
            # 尝试提取零件号（字母数字组合，>5位，不含全数字的年份/日期）
            nums = re.findall(r'\b([A-Z0-9]{5,}[A-Z0-9]?)\b', line)
            for n in nums:
                if n.isdigit() and len(n) <= 6:
                    continue  # 跳过纯数字（可能是日期或序号）
                if n.isdigit() and len(n) > 6:
                    continue
                parts.append({
                    "part_number": n,
                    "description": line[:150],
                    "source": "17vin_epc_cdp"
                })
        i += 1
    return parts

# ============================================================
# 主流程
# ============================================================
def query_vehicle_parts(brand, series, year=None, part_keywords=None):
    """
    通过 17vin CDP EPC 查询指定车型的配件 OE 号。
    返回: list[dict] — 匹配的零件列表
    """
    if part_keywords is None:
        part_keywords = DEFAULT_PART_KEYWORDS

    cdp = CDPClient(tab_keyword="17vin")
    try:
        # 0. 始终先回首页
        cdp.navigate("https://www.17vin.com/", wait=4)
        time.sleep(1)

        # 1. 点击"车型查询"进入 EPC 模式，如果失败则重新导航首页
        r = cdp.click_text("车型查询")
        if "not found" in str(r):
            cdp.navigate("https://www.17vin.com/", wait=4)
            cdp.click_text("车型查询")

        # 2. 选择品牌
        step_select_brand(cdp, brand)

        # 3. 选择车系
        result = step_select_series(cdp, series)
        if "not found" in str(result):
            # 尝试在品牌页面直接搜索车系
            text = cdp.get_text()
            if series not in text:
                print(f"[ERROR] Series '{series}' not found for brand '{brand}'")
                return []

        # 4. 选择车型（第一个有 EPC 目录的）
        epc_url = step_select_model(cdp, year=year)
        if not epc_url:
            # 如果页面已经在 cata1，跳过 model 选择
            cur = cdp.eval_js("window.location.href") or ""
            if "/cata1/" not in cur:
                print(f"[ERROR] No EPC catalog available for {brand} {series}")
                return []

        # 5. 进入底盘一级目录 → 二级目录
        cata2_ok = step_find_cata1(cdp)
        if not cata2_ok:
            print("[ERROR] Could not navigate to cata2 (CHASSIS)")
            return []

        # 6. 进入前桥二级目录 → 零件列表
        partlist_ok = step_find_cata2(cdp)
        if not partlist_ok:
            print("[ERROR] Could not navigate to partlist (FRONT AXLE)")
            return []

        # 7. 提取配件 OE 号
        parts = step_extract_parts(cdp, keywords=part_keywords)
        return parts

    finally:
        cdp.close()


# ============================================================
# 批量查询
# ============================================================
def batch_query(vehicles, part_keywords=None):
    """
    批量查询多款车型。

    vehicles: list of dict — [{"brand": "现代", "series": "瑞纳", "year": "2014"}, ...]
    返回: dict — { "现代_瑞纳": [parts], ... }
    """
    results = {}
    for i, v in enumerate(vehicles):
        brand = v["brand"]
        series = v["series"]
        year = v.get("year")
        key = f"{brand}_{series}"
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(vehicles)}] Querying: {brand} {series} ({year or 'any'})")
        print(f"{'='*60}")
        try:
            parts = query_vehicle_parts(brand, series, year, part_keywords)
            results[key] = parts
            if parts:
                for p in parts:
                    print(f"  → OE: {p['part_number']} | {p['description'][:80]}")
            else:
                print(f"  → No matching parts found")
        except Exception as e:
            print(f"  → ERROR: {e}")
            results[key] = []
    return results


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="17vin EPC CDP 导航器")
    parser.add_argument("--brand", required=True, help="品牌名，如 现代/丰田/本田")
    parser.add_argument("--series", required=True, help="车系名，如 瑞纳/威驰/飞度")
    parser.add_argument("--year", help="年份，如 2014")
    parser.add_argument("--part", default="轮毂轴承", help="目标配件关键词")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    keywords = args.part.split(",")
    parts = query_vehicle_parts(args.brand, args.series, args.year, keywords)

    if args.json:
        print(json.dumps(parts, ensure_ascii=False, indent=2))
    else:
        print(f"\n=== {args.brand} {args.series} 前轮轴承 OE 号 ===")
        if parts:
            for p in parts:
                print(f"  OE: {p['part_number']}")
                print(f"  Desc: {p['description'][:100]}")
        else:
            print("  未找到匹配配件（可能需要调整关键词或品牌在17vin无覆盖）")
