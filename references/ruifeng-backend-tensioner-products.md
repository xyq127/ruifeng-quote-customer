# 睿锋后台API速查

## 登录

```bash
# WSL中DNS失败，需IP直连
curl -sk -X POST "https://8.155.164.3/api/oauth/login/dologin?mobile=13999999999&password=999999" \
  -H "Host: rfscm.com" -H "User-Agent: Mozilla/5.0"
```
```python
# Python - 注意字段名是 token 不是 access_token
r = session.post(f"{BASE}/api/oauth/login/dologin?mobile=13999999999&password=999999")
token = r.json()["data"]["token"]
```

## 分类搜索（涨紧轮）

```python
resp = session.get(f"{BASE}/api/principal/product/list",
    params={"page": 1, "size": 100, "queryType": "ENCODE",
            "categoryIds": "655709386127314944", "queryThird": "false"})
# 响应：data.content[].products, data.totalPages, data.totalElements
```

## 关键词搜索

```python
resp = session.get(f"{BASE}/api/principal/product/list",
    params={"page": 1, "size": 20, "queryType": "ENCODE",
            "keyword": "搜索词", "queryThird": "false"})
```

## 常见问题

- 涨紧轮分类ID: 655709386127314944 → 668条
- keyword"张紧器"→ 44条，"张紧轮"→ 50条，"惰轮"/"过渡轮"→ 0条
- OE号搜索需去掉横杠（25281-2B000 → 252812B000）
- 张紧器OE尾缀315（总成）vs 341（液压缸单独件）
