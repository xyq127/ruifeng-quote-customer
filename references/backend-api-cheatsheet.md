# 睿锋后台 API 速查表

> 来源：2026-05-12 从 Java 后端代码（ProductController.java + Product.java）提取
> 环境：正式环境 `https://rfscm.com`

## ⚠️ 重要限制：运营账号 API 不可用（2026-05-15 确认）

**运营账号（mobile=13999999999, password=999999）的 `/product/list` 接口对所有搜索条件均返回空数据。**

- `code`、`oe`、`name`、`pageNum`/`pageSize` 参数均无效
- `findById` 对某些ID返回 `data: null`
- CDP 前端页面加载 SPA 但内容为空（app.fb0fcc9c.js），无法通过 CDP 操作
- `/product/list/batch`、`/product/findByCode`、`/product/detail` 均返回 404 或空

**正确方式：用户通过后台浏览器 UI 搜索 → 截图发送 → Agent 从截图提取结果。**

搜索框输入 8位数字（如 `44825037`）可匹配到 **OE列** 或 **工厂编号列** 包含该数字的所有产品。

### 登录
```
POST https://rfscm.com/api/oauth/login/dologin?mobile=13999999999&password=999999
Content-Type: application/json

Response: {"code": 200, "data": {"token": "...", "userId": "..."}}
```
⚠️ 返回 `code: 200`，不是 `code: 1`。不走代理（设置 no_proxy）。

### 调用业务接口
```
GET https://rfscm.com/api/principal/xxx?param=value
Authorization: Bearer {token}
```

## 核心接口

| 接口 | 方法 | 说明 | 返回格式 |
|------|------|------|---------|
| `/product/list` | GET | 搜索产品 | data=JSON **字符串** |
| `/product/list/batch` | GET | 批量搜索 | data=dict |
| `/product/findById` | GET | 产品详情 | data=dict |
| `/productNumDetail/list` | GET | 关联编号 | data=JSON **字符串** |
| `/productThirdOem/list` | GET | 第三方 OE | data=JSON **字符串** |
| `/productImage/list` | GET | 产品图片 | data=JSON **字符串** |
| `/productParamDetail/list` | GET | 产品参数 | data=JSON **字符串** |

## Product 实体关键字段

```json
{
  "id": "002481",
  "num": "1003002481",       // 产品编号（我们系统的）
  "code": "DAC397200372RZ(ABS88)",  // 工厂编号
  "oe": "DG80-33-047",       // OE 号
  "name": "双列球轴承",
  "brand": "精峰",
  "car": "福特",
  "mainVehicleModel": "福特嘉年华（11-15款）、翼博（13-16款）、马自达2两厢（07-15款）",
  "referenceVehicleModel": "福特嘉年华",
  "abcCategory": "A",
  "saleSort": 1256,
  "supplierName": "杭州雷迪克节能科技股份有限公司",
  "partId": "1223237",
  "radicalSupport": 2,        // 0=无对应雷迪克, 1=存在对应, 2=雷迪克本身
  "warranty": "2年6万公里",
  "purchasePrice": 28.34,
  "salePrice": 37.79,
  "status": 1,                // 0=新品, 1=已上架, 2=已下架
  "categoryId": "655709069176344576",
  "categoryName": "双列球轴承",
  "numDetails": [...],        // 关联编号（queryThird=true 时返回）
  "thirdOems": [...],         // 第三方 OE
  "images": [...],            // 图片列表
  "paramDetails": [...]       // 参数明细
}
```

## 产品参数示例（ID 002481）

```
重量 = 0.592
内径 = 38.993    // 工厂编号中 39 的精确值
外径 = 72
内圈高 = 18.5
外圈高 = 37
极数 = 88        // 对应 ABS88
ABS(是/否) = 是
```

## 关联编号来源映射

| originalSource | 来源 |
|---------------|------|
| 0 | PDE |
| 1 | 雷迪克沃众轴承型号对照表 |
| 2 | 瓦轴数据 |
| 3 | 手动添加 |

## Python 统一处理函数

```python
def parse_data(r):
    """统一处理 data 字段，可能是 dict 或 JSON 字符串"""
    if isinstance(r['data'], dict):
        return r['data']
    return json.loads(r['data'])
```
