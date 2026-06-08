#!/usr/bin/env python3
"""快速批量: 已知OE → 17vin partsearch → 替换号 → 睿锋后台"""
import websocket, json, time, urllib.request, requests, os

CDP_HOST = "http://localhost:9250"
RF_BASE = "https://8.155.164.3"
os.environ['no_proxy'] = '127.0.0.1,localhost,::1,rfscm.com,8.155.164.3'

# === 睿锋登录 ===
session = requests.Session()
session.headers["Host"] = "rfscm.com"
session.verify = False
session.trust_env = False
r = session.post(f"{RF_BASE}/api/oauth/login/dologin?mobile=13999999999&password=999999")
token = r.json().get("data",{}).get("token","")
print(f"[睿锋] Login OK")

def rf_search(kw):
    r = session.get(f"{RF_BASE}/api/principal/product/list",
        params={"page":1,"size":10,"queryType":"ENCODE","keyword":kw,"queryThird":"false"})
    return [{"id":p.get("id"),"code":p.get("code"),"oe":p.get("oe"),
             "name":p.get("name"),"car":p.get("car")} for p in
            r.json().get("data",{}).get("content",[])]

# === CDP ===
pages = json.loads(urllib.request.urlopen(f"{CDP_HOST}/json/list").read())
vin_tab = [p for p in pages if "17vin" in p.get("url","")][0]
ws = websocket.create_connection(vin_tab["webSocketDebuggerUrl"], timeout=15, http_proxy_host="", http_proxy_port=None)
mid=[0]
def js(expr, t=10):
    mid[0]+=1
    ws.send(json.dumps({"id":mid[0],"method":"Runtime.evaluate","params":{"expression":expr,"returnByValue":True}}))
    ws.settimeout(t); t0=time.time()
    while time.time()-t0<t:
        try:
            msg=json.loads(ws.recv())
            if msg.get("id")==mid[0]: return msg.get("result",{}).get("result",{}).get("value")
        except: break
    return None
def nav(url, wait=4):
    ws.send(json.dumps({"id":mid[0]+100,"method":"Page.navigate","params":{"url":url}})); mid[0]+=100
    time.sleep(wait)

def partsearch(oe):
    """17vin partsearch → 获取配件信息和替换号链接"""
    oe_clean = oe.replace("-","").replace(" ","")
    nav(f"https://www.17vin.com/partsearch/{oe_clean}.html", 6)
    # 获取 brand 和 替换号链接
    info = js("""
(function(){
    let rows = document.querySelectorAll('tr');
    let brand = '', name = '';
    for(let r of rows) {
        let cells = r.querySelectorAll('td');
        if(cells.length>=2 && cells[1].textContent.includes('"""+oe_clean+"""')) {
            brand = cells[0]?.textContent?.trim()||'';
            name = cells.length>=3 ? cells[2].textContent.trim() : '';
        }
    }
    let ilink = '';
    for(let a of document.querySelectorAll('a')) {
        if(a.textContent.includes('替换号')) { ilink = a.href; break; }
    }
    return JSON.stringify({brand,name,ilink});
})()
""")
    try: info = json.loads(info)
    except: info = {}
    return info

def interchange(ilink):
    """获取替换号列表"""
    if not ilink: return []
    nav(ilink, 6)
    oems = js("""
(function(){
    let found = [];
    let rows = document.querySelectorAll('tr');
    for(let r of rows) {
        let cells = r.querySelectorAll('td');
        if(cells.length>=2) {
            let pn = cells[1].textContent.trim().replace(/复制成功/g,'');
            if(/^[A-Z0-9][A-Z0-9-]{4,}/.test(pn) && !pn.includes('品牌') && !pn.includes('替换'))
                found.push(pn);
        }
    }
    return JSON.stringify(found.slice(0,15));
})()
""")
    try: return json.loads(oems)
    except: return []

# === 8行数据: 已知OE号列表 (来自电商+网络验证) ===
rows = [
    {"row":"1,4","desc":"现代瑞纳/K2 PB","oe":"5172002000","dac":"DAC38700037"},
    {"row":"2","desc":"丰田威驰/雅力士 XP90","oe":"435020D101","dac":"DAC40750039"},
    {"row":"2","desc":"吉利金刚","oe":"9004363214","dac":"DAC3870DW"},
    {"row":"3","desc":"本田飞度GK5","oe":"44300T5GH51","dac":"38BWD27"},
    {"row":"5,6","desc":"别克凯越 J-body","oe":"96995000","dac":"09161454"},
    {"row":"7","desc":"大众桑塔纳2000","oe":"1J0498625","dac":"DAC39680037"},
    {"row":"8","desc":"大众宝来/朗逸 PQ34","oe":"1J0498625","dac":"DAC39680037"},
]

total_t0 = time.time()
results = []

for i, row in enumerate(rows):
    t0 = time.time()
    oe = row["oe"]
    dac = row["dac"]
    desc = row["desc"]
    print(f"\n[{row['row']}] {desc} | OE={oe}")

    # Step 1: 17vin partsearch
    info = partsearch(oe)
    brand = info.get("brand","?")
    ilink = info.get("ilink","")
    print(f"  17vin品牌: {brand} | 替换号链接: {'有' if ilink else '无'}")

    # Step 2: 替换号
    oems = interchange(ilink) if ilink else []
    print(f"  替换号(前5): {oems[:5]}")

    # Step 3: 睿锋后台搜索
    rf1 = rf_search(oe)
    rf2 = rf_search(dac) if not rf1 else []
    rf = rf1 + rf2
    print(f"  睿锋产品: {len(rf)}个")

    if rf:
        rf_top = rf[0]
        print(f"  雷迪克编号: {rf_top.get('code','?')} | {rf_top.get('name','?')} | {rf_top.get('car','?')}")

    elapsed = time.time()-t0
    results.append({**row, "brand_17vin":brand, "interchange":oems[:5],
                    "rf_products":rf[:3], "elapsed":round(elapsed,1)})
    print(f"  ⏱ {elapsed:.1f}s")

total = time.time()-total_t0
print(f"\n{'='*60}")
print(f"总计用时: {total:.1f}s ({total/60:.1f}min) | 平均: {total/len(rows):.1f}s/车")
print(f"{'='*60}")

# === 汇总表 ===
print(f"\n{'行':<6} {'车型描述':<24} {'17vin OE':<16} {'品牌件':<20} {'雷迪克编号':<22} {'用时'}")
print("-"*95)
for r in results:
    oe = r["oe"]
    rf0 = r["rf_products"][0] if r["rf_products"] else {}
    print(f"Row{r['row']:<4} {r['desc']:<24} {oe:<16} {r.get('brand_17vin','?'):<20} {rf0.get('code','?'):<22} {r['elapsed']}s")

print(f"\n=== JSON ===\n{json.dumps(results, ensure_ascii=False, indent=2)}")

ws.close()
