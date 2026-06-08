# 泰安联/TecDoc 搜索结果模式总结

## 搜索结果数据结构

泰安联搜索结果页面以表格形式呈现，每行一个产品，4列：
1. 图片/品牌：产品图片 + 品牌 Logo
2. 基本信息：产品编号(h2) + 品牌名称(h2) + 产品类型 + 状态
3. OE号：按车厂分类的原始 OE 编号列表
4. 参数：内径/外径/高度/安装位置/补充信息等

## 参数缺失模式（2026-06）

**JSPT、READYGOO 等国产小品牌**：参数列全部为"-"，无尺寸数据。
- 必须进入产品详情页查看产品图片（图上可能标注尺寸）
- 产品详情页可能超时或报错（500 风格错误页）

**LYNXAUTO 部分产品**：仅有安装位置，无尺寸数据。

**RRT-CN**：高度显示异常值（如 3mm、5mm），可能是数据录入错误。

## 大品牌覆盖情况（实测）

| 品牌 | 参数完整度 | 备注 |
|------|----------|------|
| FEBEST | ✅ 完整 | 带对比号查询标识 |
| BLUE PRINT | ✅ 完整 | 部分结果缺高度 |
| 费比(febi bilstein) | ⚠️ 部分 | 搜索结果中缺高度/外径，需点进详情页 |
| SWAG | ⚠️ 部分 | 同费比 |
| SKF(斯凯孚) | ✅ 完整 | 仅显示 OE 号对应关系，参数需看详情页 |
| 冠盛(GSP) | ✅ 完整 | GK 前缀编号 |
| LYNXAUTO | ⚠️ 部分 | 常缺尺寸数据 |

## 搜索方式差异

**通过产品号查询**（如 DAC34640037）：
- 匹配到同编号或对比号的产品
- 标注"通过产品号查询"或"通过对比号查询"

**通过OE号查询**（如 9064166）：
- 匹配到适配该 OE 的所有品牌产品
- 标注"通过OE号查询"
- 结果数量通常更多（14+个）
- 包含大厂 OEM（SKF、FAG 等），是交叉验证的最佳渠道

## JS 提取模板

```javascript
// 提取搜索结果表格中所有产品
const rows = document.querySelectorAll('table tbody tr');
const results = [];
rows.forEach((row) => {
  const cells = row.querySelectorAll('td');
  if (cells.length >= 4) {
    const brandCell = cells[1];
    const paramCell = cells[3];
    const headings = brandCell.querySelectorAll('h2');
    const partNum = headings[0]?.textContent?.trim() || '';
    const brand = headings[1]?.textContent?.trim() || '';
    const params = paramCell.textContent.replace(/\s+/g, ' ').trim();
    const id = params.match(/内径.*?:\s*(\d+)/)?.[1] || '-';
    const od = params.match(/外径.*?:\s*(\d+)/)?.[1] || '-';
    const w = params.match(/高度.*?:\s*(\d+)/)?.[1] || '-';
    if (partNum) {
      results.push({ partNum, brand, id, od, w });
    }
  }
});
JSON.stringify(results, null, 2);
```

## 17vin EPC 覆盖确认

**铃木**：全系"无epc目录数据"（昌河铃木、长安铃木、铃木进口）
**雪佛兰**：有 EPC 目录（需进一步确认具体车型）
**通用汽车**：有 EPC 目录

17vin EPC URL 规律：`https://www.17vin.com/brand/{品牌英文}.html`
