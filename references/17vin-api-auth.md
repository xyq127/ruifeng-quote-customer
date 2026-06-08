# 17vin API 认证方式对照

睿锋智链数据清洗中涉及两个17vin API体系，认证方式不同。

## 旧 API (api.17vin.com:8080)

- **认证**: MD5 token，`token = MD5(MD5(user) + MD5(pass) + url_params)`
- **可用接口**: Section 6 (6001品牌/6003车型/6101-6105目录/6108搜索)
- **不可用接口**: Section 4 (4001 search_epc / 4004 替换号 / 40031 适配车型) → 返回503，需要额外付费开通
- **账户**: `ruifengzhilian` / `JSD9Wd2`
- **特点**: GET请求，参数拼在URL里

### Python 示例

```python
import hashlib

def generate_token(username, password, url_params):
    username_md5 = hashlib.md5(username.encode()).hexdigest()
    password_md5 = hashlib.md5(password.encode()).hexdigest()
    token_str = f"{username_md5}{password_md5}{url_params}"
    return hashlib.md5(token_str.encode()).hexdigest()

# 6001 品牌列表
url_params = "/?action=brands"
token = generate_token("ruifengzhilian", "JSD9Wd2", url_params)
url = f"http://api.17vin.com:8080{url_params}&user=ruifengzhilian&token={token}"
```

## 新 API (SFH Open API)

- **域名**: `https://openapi.sfh123.cn`
- **认证**: HMAC-SHA256 签名，通过请求头传递
- **头部**: `X-App-Key`, `X-Timestamp`, `X-Nonce`, `X-Signature`
- **账户**: app_key=`91161acaf7824c38942f59266fb437c6`, app_secret=`5fef2ea2227eb24233967df4a667db585eeb6dee2fae206d199b82122bb90548aa1614b5ef30b965`
- **方法**: POST，JSON body
- **接口**:
  - `POST /open-api/v1/vin/query` — VIN解析
  - `POST /open-api/v1/parts/query` — 按车型ID查配件（不支持OEM反向）
  - `POST /open-api/v1/vehicle-selector/makers` — 品牌列表
  - `POST /open-api/v1/vehicle-selector/series` — 车系列表
  - `POST /open-api/v1/vehicle-selector/vehicles` — 车型列表

### Signature 算法

1. 组合待签名字符串：`{app_key}\n{timestamp}\n{nonce}\n{method}\n{path}\n{body_sha256}`
2. 用 app_secret 做 HMAC-SHA256
3. 转十六进制字符串

```python
import hmac, hashlib

sign_str = f"{app_key}\n{timestamp}\n{nonce}\nPOST\n/open-api/v1/vin/query\n{body_sha256}"
signature = hmac.new(app_secret.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
```

### 关键发现

- SFH API **不支持** OEM反向查替换号/适配车型（需要 Section 4 旧API，但账户无权限）
- SFH 的 `parts/query` 需要 `vehicleIds` 参数，按车型查配件
- 当前可用的 OEM 反向查询来源：**泰安联 (TecDoc)** 通过 CDP 浏览器搜索
