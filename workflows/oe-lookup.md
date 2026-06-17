# OE 查询工作流

## 触发条件

用户输入：OE 号 / 工厂编号(DAC/DU/RAH) / 尺寸规格 / 车型+配件名

**示例：**
- `DAC39720037-2RZ(ABS88)` — 工厂编号
- `45x84x45` — 尺寸规格
- `31110-RAA-A01` — OE 号
- `本田雅阁2.4L 涨紧轮` — 车型+配件名

---

## Plan：输入识别与策略制定

### Step 1: 识别输入类型

| 正则模式 | 类型 | 采样 |
|---------|------|------|
| `^DAC\d{8}` `^DU\d{8}` `^GDU\d{8}` | 一代轴承工厂编号 | `DAC39720037` |
| `^RAH\d+` `^RAW\d+` | 轮毂单元编号 | `RAH123456` |
| `^\d{2,3}[x×]\d{2,3}[x×]\d{2,3}` | 尺寸规格 | `45x84x45` |
| `^[A-Z]{1,3}\d{6,15}` | OEM/关联编号 (疑似) | `31110RAAA01` |
| 含中文 | 车型描述 | `本田雅阁2.4L` |

### Step 2: 根据输入类型制定计划

| 输入类型 | 执行策略 |
|---------|---------|
| **一代轴承工厂编号** | parse → 提取8位核心编号 → oe-query(DAC编码) → backend-search → verify |
| **轮毂单元编号** | 从后台取参数 → oe-query → verify |
| **尺寸规格** | oe-query(dimensions) → backend-search → verify |
| **OE/关联编号** | backend-search → backend-detail → cross-validate → verify |
| **车型描述** | 行话翻译(查表) → oe-query → verify；--deep 时走 17vin CDP |
| **无法识别** | 询问用户明确输入类型 |

### Step 3: 数据源策略

| 产品类型 | 优先数据源 | 备选 |
|---------|-----------|------|
| 一代轴承 | 泰安联 DAC编码搜索 `{d}{D}00{B}` | 17vin → 电商平台 |
| 轮毂单元 | 17vin EPC / 后台 API | 泰安联 → 电商平台 |
| 涨紧轮/惰轮 | 17vin 配件搜索 | 后台 API → 泰安联 |
| 中国自主品牌 | 电商平台 (3店铺验证) | 17vin → 后台 |

泰安联和 17vin 同级并行查询，任一命中即可进入 verify。

---

## Execute：逐步执行

### Step 1: 工厂编号解析（仅工厂编号输入）

```bash
# 命令
cli-anything-platform-service --json data-clean parse <编号>

# 输入: factory_number (string)
# 输出:
# {
#   "prefix": "DAC",
#   "inner_diameter": 39,
#   "outer_diameter": 72,
#   "variant": 0,
#   "height": 37,
#   "core_8digit": "39720037",
#   "has_abs": true,
#   "abs_teeth": 88,
#   "is_parsable": true
# }
```

**失败处理：** `is_parsable: false` → 标记 "无法解析"，跳过 Step 2，直接进入 Step 3 用原始编号搜索后台。

### Step 2: 多源 OE 查询

```bash
# 一代轴承（DAC编码格式）
cli-anything-platform-service --json data-clean oe-query --query "45840045"

# 尺寸规格
cli-anything-platform-service --json data-clean oe-query --query "45x84x45"

# OE 号
cli-anything-platform-service --json data-clean oe-query --query "31110-RAA-A01"
```

**输出：**
```json
{
  "query": "45840045",
  "input_type": "dac",
  "tecalliance": [
    {"brand": "TOYOTA", "oe": "90363-45050", "description": "..."}
  ],
  "17vin": [
    {"brand": "TOYOTA", "oe": "90363-45050", "vehicle": "..."}
  ],
  "cache_hit": true
}
```

**失败处理：**
- 泰安联不可达（CDP 9250 不通）→ 跳过，仅用 17vin
- 17vin API 返回 503 → 检查 `no_proxy` 环境变量，重试
- 两源均无结果 → 进入电商兜底 (Step 4)

### Step 3: 后台已有记录查询

```bash
# 用 Step 2 获取的 OE 号回查后台
cli-anything-platform-service --json data-clean backend-search --keyword "90363-45050" --with-details
```

**注意：** 必须带 `queryType=ENCODE`（CLI 已内置），返回字段为 `data.content`（不是 `records`）。

**输出：** 匹配到的产品列表，含 productId、code、oe、关联编号、参数。

**失败处理：** 后台无匹配 → 标记 "需补充"，跳过。不阻断后续。

### Step 4: 电商平台兜底（仅当 Step 2 两源全空时）

搜索 `"{车型} {配件名} OE号"`（淘宝/京东/1688）。

**可靠性要求：** 至少 3 家不同店铺列出相同的 OE 号才可采纳。
优先采信实物图 OE 钢印。

---

## Verify：数据校验

### 校验规则

| # | 规则 | 判定 |
|---|------|------|
| 1 | 泰安联 ∩ 17vin 交集非空 | ✅ 高可信 |
| 2 | 泰安联 ∩ 17vin 交集为空，但各有一致车型 | ⚠️ 需人工确认，可能同一零件不同代工厂 |
| 3 | 后台已有匹配 | 记录 productId，标记 "已入库" |
| 4 | 后台无匹配 | 标记 "需补充"，输出可回写的 OE 列表 |
| 5 | 电商平台 3+ 店铺一致 | ⚠️ 采纳但标记 "电商验证"，可信度较低 |
| 6 | 仅单源命中 | ⚠️ 标记 "单源待确认" |
| 7 | 全部未命中 | ❌ 标记 "待工厂确认" |

### 置信度分级

| 等级 | 条件 | 说明 |
|------|------|------|
| **A-确认** | 泰安联+17vin+后台三者一致 | 可直接回写，无需人工审核 |
| **B-待补充** | 两源一致，后台无记录 | 可回写，建议人工扫一眼 |
| **C-待确认** | 仅单源命中或源间不一致 | 必须人工确认后回写 |
| **D-兜底** | 全部未命中，仅有电商数据或完全无数据 | 需工厂提供 OE |

---

## 输出格式

执行完成后，Agent 应按以下结构输出结果：

```
## OE 查询结果

**输入:** DAC39720037-2RZ(ABS88)
**类型:** 一代轴承

### 解析参数
| 内径 | 外径 | 变型 | 高度 | ABS |
|------|------|------|------|-----|
| 39mm | 72mm | 00 | 37 | 88齿 |

### 多源查询结果
| 数据源 | OE 号 | 品牌 | 车型 | 状态 |
|--------|-------|------|------|------|
| 泰安联 | 90363-45050 | TOYOTA | Corolla 2003 | ✅ |
| 17vin | 90363-45050 | TOYOTA | Corolla (E120) | ✅ |
| 后台 | — | — | — | 未入库 |

### 校验结论
**置信度: B-待补充** — 泰安联与17vin一致，但后台未找到对应产品。

### 可执行操作
- [ ] 回写 OE `90363-45050` 到后台产品 `productId=xxx`
- [ ] 补充参数：内径 39mm, 外径 72mm
```
