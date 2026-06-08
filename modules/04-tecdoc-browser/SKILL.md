---
name: ruifeng-tecdoc-browser
description: 通过浏览器操作 TecDoc 网页查询 OE 号。用户先登录，Agent 操作已登录浏览器搜索配件、获取 OE 号和适配信息。
version: 1.0.0
author: Hermes Agent
category: data-cleaning
---

# TecDoc 网页查询

## 概述

通过浏览器自动化操作 TecDoc（全球权威汽车配件目录）网页，查询配件的 OE 号和适配车型信息。作为数据清洗中的第三方数据源，用于 OE 号交叉验证。

## 登录方式

- **用户先登录**：Agent 不处理登录页面的验证码或认证流程
- 用户登录完成后通知 Agent "已登录 TecDoc"
- Agent 操作已登录的浏览器进行搜索和查询

## 查询流程

### 按 OE 号查询

```
输入：OE 号（如 DG80-33-047A）
    │
    ▼
在 TecDoc 搜索框输入 OE 号
    │
    ▼
获取匹配结果
    │
    ▼
提取：
  - 对应车型
  - 配件类别
  - 制造商信息
  - 其他关联 OE
```

### 按车型查询

```
输入：车型（如 Ford Fiesta 2011-2015）
    │
    ▼
选择品牌 → 车系 → 年款
    │
    ▼
进入配件目录
    │
    ▼
定位到轮毂轴承分类
    │
    ▼
提取该车型所有轮毂轴承的 OE 号
```

### 按工厂编号查询

```
输入：工厂编号（如 DAC39720037）
    │
    ▼
在 TecDoc 中搜索该编号
    │
    ▼
获取匹配的 OE 号和适配信息
```

## Browser 操作模板

### 1. 导航到搜索页面

```python
browser_navigate(url="TecDoc 搜索页面 URL")
```

### 2. 输入搜索条件

```python
browser_type(ref="@eX", text="DG80-33-047A")
browser_click(ref="@eS")  # 点击搜索
```

### 3. 获取结果

```python
browser_snapshot()  # 获取页面内容
# 或
browser_vision(question="请查看搜索结果，提取所有 OE 号和对应的车型信息")
```

### 4. 截图产品图片

```python
browser_vision(question="请截图当前产品的详细信息和图片")
```

## 数据提取目标

| 字段 | 用途 |
|------|------|
| OE 号 | 与睿锋后台、17vin、泰安联交叉验证 |
| 适配车型 | 验证 OE-车型映射 |
| 配件类别 | 确认是否为轮毂轴承 |
| 制造商 | 确认品牌来源 |
| 关联 OE | 补充关联编号列表 |

## 登录信息

- **网址**: `https://www.tecalliance.cn/cn/`
- **登录方式**: 用户手动完成登录（可能涉及验证码），通知 Agent 继续

## 注意事项

1. **用户先登录**：Agent 不处理登录流程
2. **TecAlliance 中国版**：已配置为 `.tecalliance.cn` 域名，中文界面
3. **搜索精度**：TecDoc 搜索可能需要精确的 OE 号格式（带/不带横杠都试一下）
4. **图片比对由用户判断**：截图后发给用户肉眼判断

## 与数据清洗流程的关系

TecDoc 是最高权威的第三方数据源（S 级来源），其 OE 号可作为"黄金标准"进行校验：

```
17vin OE + 泰安联 OE + TecDoc OE
              ↓
         交叉验证
              ↓
    一致 → 确认 OE 正确
    不一致 → 标记为待人工确认
```
