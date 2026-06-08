# 17vin SFH Open API 探索记录

## 概述

17vin 提供两套 API 体系：
1. **旧 API**: `api.17vin.com:8080` — MD5 token 鉴权，用于车型/EPC/配件查询
2. **新 SFH API**: `openapi.sfh123.cn` — HMAC-SHA256 鉴权，用于 VIN 解析/配件查询

## 新 SFH API 凭证

从 `C:\Users\Lenovo\Documents\开放API文档\开放API文档\app_key和app_secret，请妥善保存.xlsx` 获取：

| 字段 | 值 |
|------|-----|
| app_key | `91161acaf7824c38942f59266fb437c6` |
| app_secret | `5fef2ea2227eb24233967df4a667db585eeb6dee2fae206d199b82122bb90548aa1614b5ef30b965` |

## 鉴权方式

HMAC-SHA256 签名，请求头包含：

| Header | 说明 |
|--------|------|
| X-App-Key | 身份标识 |
| X-Timestamp | 毫秒时间戳 |
| X-Nonce | 每次请求唯一随机串 |
| X-Signature | HMAC-SHA256 签名 |
| Content-Type | `application/json` |

### 签名算法

```
待签名字符串 = app_key + "\n" + timestamp + "\n" + nonce + "\n" + method + "\n" + path + "\n" + SHA256(body)
signature = HMAC-SHA256(app_secret, 待签名字符串)
```

### Python 实现

```python
import hashlib, hmac, uuid, time, json

def sfh_sign(app_key, app_secret, method, path, timestamp, nonce, body_str=""):
    body_hash = hashlib.sha256(body_str.encode()).hexdigest() if body_str else hashlib.sha256(b"").hexdigest()
    sign_str = f"{app_key}\n{timestamp}\n{nonce}\n{method}\n{path}\n{body_hash}"
    return hmac.new(app_secret.encode(), sign_str.encode(), hashlib.sha256).hexdigest()

def sfh_call(path, body=None):
    ts = str(int(time.time() * 1000))
    nonce = str(uuid.uuid4())
    body_str = json.dumps(body, ensure_ascii=False) if body else "{}"
    sig = sfh_sign(APP_KEY, APP_SECRET, "POST", path, ts, nonce, body_str)
    headers = {
        "Content-Type": "application/json",
        "X-App-Key": APP_KEY,
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "X-Signature": sig,
        "X-Request-Id": f"REQ-{uuid.uuid4().hex[:8]}"
    }
    req = urllib.request.Request(f"https://openapi.sfh123.cn{path}",
        data=body_str.encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())
```

## 可用端点

| 端点 | 用途 | 状态 |
|------|------|------|
| `/open-api/v1/vin/query` | VIN 查车型 | ✅ 可用（匹配率取决于VIN质量） |
| `/open-api/v1/vehicle-selector/makers` | 品牌列表 | 需传 `regionType` 参数 |
| `/open-api/v1/vehicle-selector/series` | 车系列表 | — |
| `/open-api/v1/vehicle-selector/vehicles` | 车型列表 | — |
| `/open-api/v1/vehicle-selector/years` | 年款列表 | — |
| `/open-api/v1/parts/query` | 按车型ID查配件 | 需 `vehicleIds` 参数 |

## 局限性

**SFH API 不支持 OEM 反向查询。** `parts/query` 接口需要先有车型 ID（vehicleId），然后查该车型使用的配件，不是通过 OEM 号找车型。

对于张紧轮/配件 OEM 反向查询，仍依赖：
- **泰安联 (TecDoc)** — 通过 CDP 浏览器搜索（需登录）
- **17vin 旧 API Section 4** — 返回 503，当前账户无权限

## 旧 API Section 4 状态

`api.17vin.com:8080` 的 Section 4 接口（编码查配件）：

| 接口 | action | 用途 | 状态 |
|------|--------|------|------|
| 4001 | `search_epc` | OE号→EPC信息 | ❌ 503 |
| 4004 | `get_interchange_from_part_number_and_group_id_plus_zh` | 替换号码 | ❌ 503 |
| 40031 | `get_modellist_from_part_number_and_group_id` | 适配车型(全车件) | ❌ 503 |
| 40032 | `get_modellist_from_part_number_and_group_id_for_aftermarket` | 适配车型(易损件) | ❌ 503 |

Section 6 接口（车型查配件）可正常使用（6001 品牌列表等），但方向是 车型→配件，不是 OEM→车型。

## 参考资料

- PDF 文档：`C:\Users\Lenovo\Documents\开放API文档\开放API文档\`
- SFH API 文档页面：`https://www.17vin.com/doc/4001.html`
- 旧 API 文档：`https://www.17vin.com/doc.html`
