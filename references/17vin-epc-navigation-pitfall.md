# 17vin EPC 网页端完整操作流程与重定向坑

## 重定向机制（2026-05-14 发现）

17vin 的 `/partlist/` 深层零件列表页有**服务器端防爬机制**：

| 访问方式 | 结果 |
|---------|------|
| `browser_navigate` 直接访问 partlist URL | ❌ 重定向回首页 |
| `window.location.href` JS 设置 partlist URL | ❌ 重定向回首页 |
| 从二级目录页通过 `<li onclick>` 触发跳转 | ✅ 正常加载零件列表 |

**原因**：17vin 服务器在 partlist 页面检查 session/referer 状态，直接访问不携带来源信息时踢回首页。

**解决方案**：不要直接 `browser_navigate` 到 partlist URL。先导航到二级目录页（cata2），然后在该页面通过 JS 提取 `<li onclick>` 中的 URL，执行 `window.location.href = url` 跳转。

## 完整操作流程（以日产天籁 43202-6CT0A 为例）

### 第1步：进入品牌页

```
browser_navigate → https://www.17vin.com/brand/nissan.html
```

直接导航到品牌页（URL规律：`/brand/{品牌英文名}.html`）。

### 第2步：找到车型系列页

从品牌页找到目标车型（天籁），提取其链接：
```javascript
// JS 提取天籁的 href
// 结果: https://www.17vin.com/series/e8ahs.html
```

### 第3步：进入车型系列页

```
browser_navigate → https://www.17vin.com/series/e8ahs.html
```

页面显示所有年款天籁车型列表。

### 第4步：找到目标年款，提取 EPC 链接

```javascript
// JS 提取包含"2018"的行
// 结果示例:
{
  "year": "2018",
  "model": "天籁 XL 智进版 国Ⅴ",
  "engine": "MR20",
  "epcLink": "https://www.17vin.com/nissan/cata1/df13e22b8e6414eb008351633de2a234/22056.html?p=aXNfbW9kZWw9MQ=="
}
```

**注意**：URL 中有两个版本的参数链接：
- 已过滤（默认）：`?p=aXNfbW9kZWw9MQ==` 
- 未过滤（完整）：URL 中 `is_vin_filter_open=1`

### 第5步：进入一级目录（cata1）

```
browser_navigate → {epcLink}
```

显示一级目录列表（发动机、传动系、行驶系等）。**这个层级不会重定向**。

### 第6步：找到轮毂轴承所在分类

在天籁车型中，轮毂轴承在 **G 行驶系（车轴、悬架、车轮）** 分类下。
提取该分类的二级目录链接：
```javascript
// 找到包含 "G AXLE" 或 "G 行驶" 的链接
// 结果: https://www.17vin.com/nissan/cata2/.../G.html?...
```

### 第7步：进入二级目录（cata2）

```
browser_navigate → {cata2_link}
```

显示子分类列表：
- 400A-003 前轴
- 401A-005 前悬架 MEMBER
- 401A-006 前悬架 STRUT
- **430A-003 后轴** ← 轮毂轴承在这里
- 431A-005 后悬架 MEMBER
- 431A-006 后悬架 ABSORBER
- 433A-003 车轮与轮胎

### 第8步：进入零件列表页（⚠️ 重定向高发区）

**❌ 错误做法**：
```
browser_navigate → https://www.17vin.com/nissan/partlist/.../2-430A_003_01.html?...
```
→ 直接被重定向回首页

**✅ 正确做法**：在当前二级目录页（cata2），通过 JS 触发 onclick：
```javascript
(function(){
  const items = document.querySelectorAll('li[onclick]');
  // 找到"后轴"对应的 item
  for (let item of items) {
    if (item.textContent.includes('后轴')) {
      const onclick = item.getAttribute('onclick');
      const match = onclick.match(/'([^']+)'/);
      if (match) {
        window.location.href = match[1];
        return 'Navigating to: ' + match[1];
      }
    }
  }
  return 'not found';
})()
```

### 第9步：读取零件列表

成功加载后，页面显示零件表格：

| 图号 | 零件号 | 零件名称 | 数量 | 标准名称 | 说明 |
|------|--------|---------|------|---------|------|
| 43202 | **43202-3TS0A** | 后轮毂带轴承总成 | 1 | 后轮毂(左) | MR20 +QR25 |
| 43207 | 43206-JE20A | 后制动盘 | 2 | 后制动盘(左) | MR20 +QR25 |
| 43207 | D3206-JE20AKV | 后制动盘 | 2 | 后制动盘(左) | MR20 +QR25 |
| 43222 | 43222-41B00 | 轮毂螺栓 | 5 | 车轮螺栓(左后) | MR20 +QR25 |

## OE 验证发现（2026-05-14）

- **Excel 中 OE**：`43202-6CT0A`
- **17vin EPC 实际 OE**：`43202-3TS0A`
- **Excel G列关联编号**：`43202-6CA0A`, `512665`, `43202-6CL0A`

三个来源都不一致，说明工厂提供的 OE 号可能有误，或该 OE 号对应不同年款/配置。

## 17vin 品牌英文映射（2026-05-14 实测）

| 品牌中文名 | 品牌英文名 | URL 格式 |
|-----------|-----------|---------|
| 日产 | nissan | /brand/nissan.html |
| 现代 | hyundai | /brand/hyundai.html |
| 奔驰 | benz | /brand/benz.html |
| 丰田 | toyota | /brand/toyota.html |
| 福特 | ford | /brand/ford.html |
| 比亚迪 | byd | /brand/byd.html |
| 长安 | changan | /brand/changan.html |
| 五菱 | wuling | /brand/wuling.html |
