---
name: ruifeng-backend-api
description: 睿锋智链后台 API 查询产品信息。包含认证、产品搜索、参数查询、关联编号、图片查询等完整接口文档。
version: 1.0.0
author: Hermes Agent
category: data-cleaning
---

# 睿锋智链后台 API

## 概述

通过 HTTP API 直接查询睿锋智链后台系统中的产品信息，获取 OE 号、关联编号、物理参数、产品图片等数据。用于数据清洗中的"内部数据"基准对比。

## 认证信息

- **正式环境地址**: `https://rfscm.com`
- **管理员账号**: `13999999999`
- **密码**: `999999`

## 认证方式

### 1. 登录获取 Token

```bash
curl -X POST "https://rfscm.com/api/oauth/login/dologin?mobile=13999999999&password=999999" \
  -H "Content-Type: application/json"
```

**响应**:
```json
{
  "code": 1,
  "data": {
    "token": "eyJhbGciOi...",
    "nickName": "管理员",
    "userId": "xxx"
  }
}
```

### 2. 使用 Token 调用业务接口

```bash
curl -X GET "https://rfscm.com/api/principal/product/list?keyword=xxx" \
  -H "Authorization: Bearer {token}"
```

## 核心接口

### 1. 产品列表查询（搜索）

```
GET /api/principal/product/list
Authorization: Bearer {token}
```

**参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 否 | 搜索关键词（产品编号、产品名、OE、车系、品牌、车型代码、分类、类型） |
| status | int | 否 | 状态: 0=新品, 1=已上架, 2=已下架 |
| categoryId | string | 否 | 分类id |
| queryThird | bool | 否 | 是否查询第三方编号（默认 false） |
| exactMatch | bool | 否 | 是否精确查询（默认 false） |
| suggestType | int | 否 | 是否为代表型号: 1=是, 0=否 |
| queryType | string | 否 | 查询类型: CAR_MODEL（车型搜索）/ ENCODE（原关键词搜索，默认） |
| page | int | 否 | 页码（默认 1） |
| size | int | 否 | 每页数量（默认 15） |

**使用示例**（按工厂编号搜索）:
```bash
curl "https://rfscm.com/api/principal/product/list?keyword=DAC39720037&size=50" \
  -H "Authorization: Bearer TOKEN"
```

**响应结构**:
```json
{
  "code": 1,
  "data": "{\"content\":[...], \"totalElements\":...}"  // 注意：data 是 JSON 字符串
}
```

### 2. 批量查询产品

```
GET /api/principal/product/list/batch
Authorization: Bearer {token}
```

**参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keywords | string | 是 | 多个关键字，使用换行符 `\n` 或逗号分割 |
| maxPerKeyword | int | 否 | 每个关键字最大返回数量（默认 100） |

**使用示例**:
```bash
curl "https://rfscm.com/api/principal/product/list/batch?keywords=DAC39720037%0ADAC39720037-2RZ&maxPerKeyword=10" \
  -H "Authorization: Bearer TOKEN"
```

### 3. 根据 ID 查询产品详情

```
GET /api/principal/product/findById?id={productId}
Authorization: Bearer {token}
```

**响应**: Product 实体（包含所有字段）

### 4. 产品关联编号列表

```
GET /api/principal/productNumDetail/list
Authorization: Bearer {token}
```

**参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| productId | string | 产品ID |

**返回**: ProductNumDetail 列表，每条包含 `num`（关联编号）、`makerName`（工厂名称）、`originalSource`（数据来源：0=PDE, 1=对照表, 2=瓦轴, 3=手动）

### 5. 第三方 OE 列表

```
GET /api/principal/productThirdOem/list
Authorization: Bearer {token}
```

**参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| productId | string | 产品ID |
| oe | string | OE号（筛选） |

**返回**: ProductThirdOem 列表，每条包含 `oem`（第三方OE）、`vehicleSeries`（车系）

### 6. 产品图片列表

```
GET /api/principal/productImage/list
Authorization: Bearer {token}
```

**参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| productId | string | 产品ID |

**返回**: ProductImage 列表，每条包含 `imageUrl`（图片地址）、`imageType`（1=实物图, 2=设计图）、`compressUrl`（压缩图）、`mainImage`（是否首图）

### 7. 产品参数明细

```
GET /api/principal/productParamDetail/list
Authorization: Bearer {token}
```

**参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| productId | string | 产品ID |

**返回**: ProductParamDetail 列表，每条包含 `name`（参数名）、`nameEn`（英文名）、`paramValue`（参数值）、`type`（类型：TEXT/NUMBER/BOOLEAN）

## Python 查询脚本

```python
import requests
import json

BASE_URL = "https://rfscm.com/api"
OAUTH_URL = f"{BASE_URL}/oauth"
PRINCIPAL_URL = f"{BASE_URL}/principal"

class RuifengAPI:
    def __init__(self, mobile: str, password: str):
        self.session = requests.Session()
        self.mobile = mobile
        self.password = password
        self.token = None
        self.login()
    
    def login(self):
        resp = self.session.post(
            f"{OAUTH_URL}/login/dologin",
            params={"mobile": self.mobile, "password": self.password}
        )
        data = resp.json()
        if data.get('code') != 1:
            raise Exception(f"登录失败: {data}")
        self.token = data['data']['token']
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def search_product(self, keyword: str, query_third: bool = True, size: int = 50) -> list:
        """搜索产品"""
        resp = self.session.get(f"{PRINCIPAL_URL}/product/list", params={
            "keyword": keyword,
            "queryThird": str(query_third).lower(),
            "size": size
        })
        data = resp.json()
        if data.get('code') != 1:
            return []
        # data.data 是 JSON 字符串，需要二次解析
        products = json.loads(data['data'])
        return products.get('content', [])
    
    def get_product_detail(self, product_id: str) -> dict:
        """获取产品详情"""
        resp = self.session.get(f"{PRINCIPAL_URL}/product/findById", params={"id": product_id})
        data = resp.json()
        if data.get('code') != 1:
            return {}
        return json.loads(data['data'])
    
    def get_related_numbers(self, product_id: str) -> list:
        """获取关联编号"""
        resp = self.session.get(f"{PRINCIPAL_URL}/productNumDetail/list", params={"productId": product_id})
        data = resp.json()
        if data.get('code') != 1:
            return []
        return json.loads(data['data']).get('content', [])
    
    def get_third_oems(self, product_id: str) -> list:
        """获取第三方 OE"""
        resp = self.session.get(f"{PRINCIPAL_URL}/productThirdOem/list", params={"productId": product_id})
        data = resp.json()
        if data.get('code') != 1:
            return []
        return json.loads(data['data']).get('content', [])
    
    def get_images(self, product_id: str) -> list:
        """获取产品图片"""
        resp = self.session.get(f"{PRINCIPAL_URL}/productImage/list", params={"productId": product_id})
        data = resp.json()
        if data.get('code') != 1:
            return []
        return json.loads(data['data']).get('content', [])
    
    def get_params(self, product_id: str) -> list:
        """获取产品参数"""
        resp = self.session.get(f"{PRINCIPAL_URL}/productParamDetail/list", params={"productId": product_id})
        data = resp.json()
        if data.get('code') != 1:
            return []
        return json.loads(data['data']).get('content', [])


# 使用示例
if __name__ == '__main__':
    api = RuifengAPI("13999999999", "999999")
    
    # 搜索产品
    products = api.search_product("DAC39720037")
    for p in products:
        print(f"产品编号: {p.get('num')}")
        print(f"OE: {p.get('oe')}")
        print(f"名称: {p.get('name')}")
        print(f"车系: {p.get('car')}")
        print(f"品牌: {p.get('brand')}")
        
        # 获取关联编号
        nums = api.get_related_numbers(p['id'])
        print(f"关联编号: {[n['num'] for n in nums]}")
        
        # 获取第三方 OE
        oems = api.get_third_oems(p['id'])
        print(f"第三方 OE: {[o['oem'] for o in oems]}")
        
        # 获取图片
        images = api.get_images(p['id'])
        print(f"图片: {[img['imageUrl'] for img in images]}")
```

## Product 实体关键字段

| 字段 | 说明 |
|------|------|
| num | 产品编号（我们系统的） |
| code | 产品代码（别人系统的） |
| oe | OE 号 |
| aliasOe | 不带横杠的 OE |
| name | 产品名称 |
| car | 车系 |
| brand | 品牌 |
| images | 产品图片列表 |
| numDetails | 关联编号明细 |
| thirdOems | 关联第三方 OE |
| paramDetails | 产品参数明细 |
| saleSort | 销售排序（瓦轴数据） |
| abcCategory | ABC 分类 |

## 注意事项

1. **Token 有效期**：Token 可能有过期时间，需要定期刷新
2. **data 字段是 JSON 字符串**：`list` 接口返回的 `data` 是 JSON 字符串，需要二次 `json.loads()`
3. **分页**：`list` 接口有分页，大数据量需要翻页获取
4. **queryThird 参数**：设为 `true` 时才会返回 `thirdOems` 数据
5. **正式环境操作谨慎**：这是生产环境，只做查询操作，不要误调用 save/update/delete 接口
