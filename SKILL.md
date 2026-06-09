---
name: ruifeng-data-cleaning
description: 睿锋智链数据清洗主流程 — 综合工厂编号解析、17vin EPC 查询、泰安联浏览器查询、睿锋后台 API 查询，对单个产品进行全维度交叉验证，输出清洗报告。数据源优先级: 泰安联≈17vin > 电商平台。在数据源查询结果中，优先选取主机大厂OE(丰田/本田/日产/大众/奔驰/宝马/现代/福特等)和关联编号大厂(SKF/NSK/FAG/冠盛/盖茨等)。
version: 2.0.0
author: Hermes Agent
category: data-cleaning
changelog: |
  2.0.1 (2026-06-09): 模块目录清理：删除冗余的 ruifeng-backend-api 模块（功能已集成到 CLI）；合并 ruifeng-taianlian-browser 和 ruifeng-tecdoc-browser 为统一的 ruifeng-tecdoc-search；所有模块 description 改为触发条件格式
  2.0.0 (2026-06-04): 移除 spareto 品牌分流；新增"车型数据清洗（行话翻译）"核心章节；统一查询路径为泰安联→17vin→电商平台
  1.0.0: 初始版本
depends_on:
  - ruifeng-factory-number-parser
  - ruifeng-17vin-epc-query
  - ruifeng-tecdoc-search
  - cloakbrowser-cli
  - cli-anything-platform-service
---

# 睿锋智链数据清洗主流程

## 概述

综合多个模块技能，对单个或批量产品进行全维度交叉验证，输出清洗报告。清洗目标是确认"工厂编号 ↔ OE ↔ 车型"三位一体映射的准确性。

## ⚡ ruifeng-cli 命令速查

数据清洗流程已集成到 `cli-anything-platform-service` CLI（`data-clean` 命令组）。

| 操作 | CLI 命令 | 说明 |
|------|---------|------|
| 工厂编号解析 | `data-clean parse <编号>` | 解析 DAC/DU/RAH → 内径/外径/高度/ABS |
| 后台产品搜索 | `data-clean backend-search --keyword <关键词>` | 查询 rfscm.com 产品库 (queryType=ENCODE) |
| 后台产品详情 | `data-clean backend-detail --product-id <ID>` | 获取关联编号和参数 |
| 17vin EPC 查询 | `data-clean epc-query --keyword <车型>` | 17vin API 车型搜索/EPC 目录 |
| 泰安联搜索 | `data-clean taianlian-search --query <编号>` | 通过 CloakBrowser CDP 搜索 TecDoc |
| OE 交叉验证 | `data-clean cross-validate --file <Excel>` | 批量校验关联编号 (A/B/C 分类) |
| Excel 处理 | `data-clean excel-process read/images/merge` | Excel 读写/图片提取/跨表合并 |

**安装**: `pip install -e ~/web-project/backend-code-repo/agent-harness[data-clean]`

**配置文件**: `~/.cli-anything-platform-service/config.json`

## ⚡ 睿锋后台 API 速查（2026-05-15 实测修正）

### 正确的产品搜索 API

**方式1：关键词搜索（返回较少，44-50条）**
```
GET https://rfscm.com/api/principal/product/list?page=1&size=20&queryType=ENCODE&keyword=关键词&queryThird=false
Authorization: Bearer {token}
```

| 参数 | 说明 |
|------|------|
| `queryType` | **必须为 `ENCODE`**（模糊搜索code/oe/num等字段） |
| `keyword` | 搜索关键词，支持8位数字、OE号、DAC编号、code |
| `queryThird` | `false`（快）或 `true`（返回numDetails/thirdOems） |
| `page` / `size` | 分页，默认 page=1, size=10 |

**方式2：分类搜索（推荐，返回全量，668条）**
```
GET https://rfscm.com/api/principal/product/list
  ?page=1&size=100&queryType=ENCODE&categoryIds=655709386127314944&queryThird=false
```
- categoryIds=655709386127314944 = 涨紧轮分类，返回 668 条（远多于 keyword 搜索）
- 惰轮/过渡轮 关键词在后台结果为 0，需搜索\"涨紧轮\"或\"张紧器\"
- 产品 code 以 RAT 开头（如 RAT2801、RAT2680、RAT2460）

**⚠️ 错误用法（全部不会返回结果）：**
- `?code=X` ❌ `?oe=X` ❌ `?pageNum=X&pageSize=Y` ❌ `?searchKey=X` ❌
- 缺少 `queryType=ENCODE` ❌

### 响应结构

```json
{"code": 200, "data": {"content": [...产品数组...], "totalPages": 1}}
```

**⚠️ `content` 不是 `records`！** 所有用 `data.records` 的脚本结果为空。

### 产品记录关键字段

```json
{"id": "008019", "num": "1008011332", "code": "DAC448250372RZ(ABS96)", "oe": "RUD100120", "name": "双列球轴承", "brand": "精峰", "car": "路虎", "abcCategory": "B"}
```

**⚠️ `code` 字段经常为空字符串**，只能通过 `oe` 字段识别。

### 关联编号 & 参数 — dict 嵌套结构

`/productNumDetail/list` 和 `/productParamDetail/list` 返回 **dict**（不是 list！），需要遍历提取：

```python
def get_list(session, token, pid, api):
    r = session.get(f'{BASE}/api/principal/{api}',
                    headers={'Authorization': f'Bearer {token}'},
                    params={'productId': pid}, timeout=15)
    d = r.json().get('data')
    if isinstance(d, list): return d
    if isinstance(d, dict):
        # 提取所有 list 值
        items = []
        for v in d.values():
            if isinstance(v, list): items.extend(v)
        return items
    return []
```

### 认证

```
POST https://rfscm.com/api/oauth/login/dologin?mobile=13999999999&password=999999
```
- 返回 `code: 200`（不是 `code: 1`）
- 不走代理（设置 `no_proxy = 'rfscm.com,localhost,127.0.0.1'`）
- **13999999999 就是管理员账号**

---

## ⚡ 批量清洗流程

> 版本 2.0 (2026-06-04): 统一查询路径为 **行话翻译预处理 → 泰安联 → 17vin → 电商平台兜底**。不再做品牌分流。

```
┌─────────────────────────────────────────────────────────────┐
│                 批量数据清洗流程                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  预处理：车型数据清洗（行话翻译）                              │
│  - 将经销商的模糊"行话"翻译为可查询的具体车型/发动机/底盘号    │
│  - 详见下方 ⚡"车型数据清洗（行话翻译）"核心章节             │
│                                                             │
│  第一步：泰安联 TecDoc 查询（优先级最高）                      │
│  - 通过 CDP 连接已登录 CloakBrowser                           │
│  - 一代轴承：用工厂编号解析出的8位核心编号搜索                  │
│  - 轮毂单元：用 OE 号或车型+配件名称搜索                       │
│  - 提取 OE 号、适配车型、参数、图片                            │
│                                                             │
│  第二步：17vin EPC 查询（泰安联未命中的产品）                  │
│  - 优先使用 17vin 配件搜索快速路径（10-30秒/产品）             │
│  - 备选：浏览器 CDP EPC 树导航（3-5分钟/车型）                 │
│  - 适用于所有品牌（网页端无品牌限制）                           │
│                                                             │
│  第三步：电商平台搜索（泰安联+17vin均未命中）                   │
│  - 淘宝/京东/1688 搜索 "{车型} {配件名} OE号"                 │
│  - 从商家标题/详情中提取 OE 号，多店铺交叉验证                  │
│  - 中国自主品牌/冷门车型的重要补充数据源                        │
│                                                             │
│  补充：17vin Section 4 API（OEM 反向查询，推荐优先使用）        │
│  - 4001 search_epc 获取 brand info + group_id                 │
│  - 4004 get_interchange 获取替换号（OE互换+品牌互换）            │
│  - 40031 get_modellist 获取适配车型                            │
│  - 走 API 速度快（0.3秒/产品），不依赖 CDP 浏览器                 │
│  - ⚠️ 需设置 no_proxy 环境变量避免代理阻断                       │
│  - 详见 references/17vin-section4-api.md                      │
│                                                             │
│  补充：宜配网号码搜索（OE验证补充）                             │
│  - URL: /search?type=number&keyword=产品编号前缀               │
│  - 覆盖约50%，只有OE号无车型信息，作为辅助验证                   │
│                                                             │
│  第四步：交叉比对 + 输出报告                                   │
│  - 多来源的 OE 对比                                           │
│  - 写入 Excel 结果表                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 何时使用

- 新产品入库前需要校验 OE 映射
- 已有产品发现数据不一致，需要排查
- 批量数据清洗（按 A 类产品优先）
- 补充缺失的关联编号
- **报价表/产品表通用清洗** — 当用户提供任何产品报价或清单Excel时，自动识别各列含义（OE/关联编号/车型/产品名），标准化为 OE号+发动机型号 的结构化底表

## ⚡ 报价表/产品表清洗

### 核心原则：自动识别列含义

收到客户的报价表或产品清单时，**不需要预先知道哪列是什么**。根据内容模式自动判断：

| 列内容特征 | 判定为 |
|-----------|--------|
| 8-12位字母数字组合，常含横杠（如 `31110-RAA-A01`、`25281-2B000`） | **OE 号** |
| 多个逗号/换行分隔的编号，或带品牌前缀的编号 | **关联编号** |
| 中文品牌+车型名+排量/年款（如"本田雅阁2.4L""霸道2700"） | **车型描述** |
| 含"轴承""张紧器""惰轮""皮带"等配件类型词 | **产品名称/类型** |

### 数据源优先级

| 优先级 | 数据源 | 说明 |
|--------|--------|------|
| 1 | 泰安联 TecDoc | CDP 浏览器查询 |
| 1 | 17vin EPC | API + 网页端查询 |
| 2 | 电商平台 | 淘宝/1688/京东，至少 3 家店铺一致才采纳 |

泰安联 ≈ 17vin 同级，均高于电商平台。

### 编号选取优先级

从数据源查到多条结果时，按以下优先级选取 OE 号：

| 优先级 | 编号类型 | 示例 |
|--------|---------|------|
| 1 | 主机大厂 OE | 丰田/本田/日产/大众/奔驰/宝马/现代/福特等，零件的设计者，编号识别度最高 |
| 2 | 关联编号大厂 | SKF/NSK/FAG/冠盛/盖茨等，给主机厂代工的一线厂商 |
| 3 | 其他小厂 | 识别度低，仅作辅助参考 |

同一个 OE 号如果在泰安联和 17vin 上都能查到同一车型，数据可信度最高。

### 清洗流程

1. 识别各列含义（OE / 关联编号 / 车型 / 产品名）
2. 如有 OE 号 → 泰安联查询 → 17vin 验证 → 确认车型适配
3. 如仅有车型描述 → 行话翻译 → 发动机/底盘号 → 泰安联/17vin → 获取 OE
4. 泰安联+17vin 均无结果 → 电商平台搜索 → 多店铺交叉验证
5. 输出：标准 OE 号 + 发动机型号 + 适配车型 + 数据来源标注

### 产品类型影响

- **惰轮/单轮/过渡轮**：放宽适配容错率（同平台不同排量通用，轴承尺寸相同即可）
- **张紧器总成**：严格限制发动机型号（阻尼机构和弹簧张力因发动机不同而异）

### 行话翻译

详见 `references/chinese-vehicle-slang-engine-translation.md`（行话→发动机→OE 映射，200+条目）。

### 防御性备注

车型描述不够确定时，必须在备注中写明匹配前提：
> "按 [具体年份/代数] [发动机型号] 匹配，不适用于 [容易混淆的其他代数/发动机]"

### 中国自主品牌

长安/比亚迪/吉利/传祺/荣威等 → 泰安联/17vin 常规覆盖外，优先电商平台验证。备注"需客户提供原厂OE或车架号"。

### 参考文件索引

| 文件 | 用途 |
|------|------|
| `references/chinese-vehicle-slang-engine-translation.md` | 行话 → 发动机型号 + OE 号翻译表（200+条目，含各品牌/车系） |
| `references/17vin-section4-api.md` | **17vin API 完整参考** — 两套路径：OE反向查询 (Section 4) + 车型→EPC→OE正向 (Section 6)，含品牌覆盖率、认证方式、所有端点 |
| `references/17vin-web-navigation.md` | 17vin Web 界面导航 — URL 模式/配件搜索/EPC 树导航/CDP 操作技巧（2026-05 实测） |
| `references/17vin-partsearch-fast-verify.md` | 17vin 配件搜索快速验证 — 三级验证法/品牌覆盖/OE号段知识/实测错误案例（2026-06 实测） |
| `scripts/17vin_epc_cdp_navigator.py` | **17vin CDP EPC 导航脚本** — 通过 CDP 浏览器自动导航 EPC 树，按车型查配件 OE 号 |
| `scripts/17vin_batch_oe_query.py` | **17vin 批量 OE 查询脚本** — partsearch → 替换号 → 睿锋后台，全链路清洗 |
| `scripts/tensioner-pricing-cleaner.py` | 张紧轮/惰轮报价清单清洗脚本 |
| `scripts/tensioner-pricing-cleaner-full.py` | 张紧轮/惰轮报价清单清洗脚本（完整版） |
| `scripts/17vin_batch.py` | 17vin Section 4 API 批量查询脚本 — 位置：`/home/stoic16/.hermes/scripts/17vin_batch.py`（含断点续传） |
| `scripts/taianlian_batch_v2.py` | 泰安联 CDP 批量查询脚本 — 位置：`/home/stoic16/.hermes/scripts/taianlian_batch_v2.py` |
| `scripts/tl_batch_run.py` | 泰安联 CDP 分批查询脚本（每30个保存一次） — 位置：`/home/stoic16/.hermes/scripts/tl_batch_run.py` |

使用前加载参考文件获取交叉数据。日系/德系/韩系走量款OE号可靠度高，中国自主品牌（长安/比亚迪/吉利等）优先走电商平台验证。

## ⚡ 车型数据清洗（行话翻译）—— 核心预处理步骤

### 为什么需要行话翻译

国内汽配经销商的车型描述是"行话"，模糊且不标准。例如：
- "本田雅阁2.4L" → 八代还是九代？发动机是 K24Z 还是 K24W？
- "霸道2700" → 不是官方车名，对应 Land Cruiser Prado 2.7L
- "新马自达6" → 不确定是哪一代，发动机可能是 LF 或 PE

**必须先将行话翻译为可查询的具体数据（品牌 + 具体车型 + 年份 + 发动机/底盘号），才能进行后续的 17vin EPC 或泰安联查询。**

### 两种产品类型的翻译路径

涨紧轮/惰轮和轮毂轴承的通用性逻辑不同，翻译路径也不同：

| 维度 | 涨紧轮/惰轮 | 轮毂轴承 |
|------|------------|---------|
| 通用性逻辑 | 同发动机型号 → 基本通用 | 同底盘代 → 基本通用 |
| 翻译目标 | 发动机型号 | 底盘号 |
| 代表车型 | 搭载该发动机的代表车型 | 该底盘代的代表车型 |
| 主要查询渠道 | 17vin EPC (配件搜索) | 泰安联 TecDoc + 17vin |
| 参考文件 | `chinese-vehicle-slang-engine-translation.md` | 工厂原表 + 底盘号速查表 |

### 路径 A：涨紧轮/惰轮（按发动机型号）

**认知基础**：同一发动机型号的车型，涨紧轮/惰轮基本通用（张紧器总成需严格确认发动机，惰轮/单轮可放宽到同平台）。

```
经销商行话
    │
    ▼
提取发动机型号（查 chinese-vehicle-slang-engine-translation.md）
    │
    ▼
找到搭载该发动机的代表车型（品牌 + 具体车型 + 年份）
 例: "本田雅阁2.4L" → K24Z → 八代雅阁 2.4L (2008-2012)
    │
    ▼
17vin 配件搜索: https://www.17vin.com/partsearch/{OE}.html
 或 17vin 网页端 EPC 树导航（如配件搜索未收录该品牌）
    │
    ▼
确认配件类型 → 获取 OE 号 → 验证车型适配
```

**翻译示例**：

| 输入行话 | 翻译后发动机 | 代表车型 | 代表OE号 |
|---------|------------|---------|---------|
| "本田雅阁2.4L" | K24Z | 八代雅阁 2.4L (2008-2012) | 31110-RAA-A01 |
| "朗逸1.6" | EA111 1.6L MPI | 朗逸 1.6L (2010-2014) | 03C903315C |
| "霸道2700" | 2TR-FE 2.7L | Land Cruiser Prado 2.7L | 16620-31070 |
| "新马自达6" | PE Skyactiv-G 2.0L | 阿特兹 2.0L (2014-2019) | PE01-15-980 |

### 路径 B：轮毂轴承（按底盘号）

**认知基础**：同一底盘代的不同车型，轮毂轴承基本通用（需区分前/后轮、带/不带 ABS）。

```
经销商行话
    │
    ▼
提取品牌+车型+代数 → 确定底盘号
    │
    ▼
找到该底盘代的代表车型（品牌 + 具体车型 + 年份）
 例: "福克斯12款" → C346底盘 → 福特福克斯 (2012-2015)
    │
    ▼
泰安联 TecDoc: 用 8位核心编号搜索
 17vin EPC: 用代表车型查 EPC 目录 → 逐级找到轮毂轴承
    │
    ▼
确认安装位置（前/后）→ 确认 ABS 状态 → 获取 OE 号
```

**常见底盘号速查（轮毂轴承用）**：

| 品牌 | 行话关键词 | 底盘号 | 代表车型 | 年款 |
|------|-----------|--------|---------|------|
| 现代/起亚 | 瑞纳/雅绅特/K2/瑞风 | PB | 瑞纳/起亚K2 | 2010-2017 |
| 福特 | 福克斯12款 | C346 | 福克斯 | 2012-2015 |
| 福特 | 嘉年华/翼博 | B2E | 嘉年华 | 2011-2016 |
| 本田 | 新飞度/新锋范/哥瑞 | GK5/GM6 | 飞度/锋范 | 2014- |
| 本田 | 八代雅阁 | CP1/CP2/CP3 | 雅阁 | 2008-2012 |
| 日产 | 逍客/奇骏T31 | J10 | 逍客 | 2007-2013 |
| 日产 | 新奇骏/新逍客 | T32/J11 | 奇骏 | 2014- |
| 大众 | 速腾/途安/高尔夫5 | PQ35 | 速腾 | 2006-2014 |
| 大众 | 朗逸/宝来/高尔夫6 | PQ34/PQ35 | 朗逸 | 2008-2016 |
| 大众 | 新桑塔纳/新捷达 | PQ25拉皮 | 新桑塔纳 | 2013- |
| 别克 | 凯越/HRV/新凯越 | J-body/T250 | 凯越 | 2003-2016 |
| 丰田 | 老雅力士/威驰1.3/1.5 | XP90 | 威驰/雅力士 | 2005-2013 |
| 丰田 | 卡罗拉 | E140/E170 | 卡罗拉 | 2007-2018 |
| 长城 | 精灵/炫丽/酷熊 | CH041/CH031 | 炫丽 | 2008-2012 |
| 吉利 | 金刚 | LG-1 | 金刚 | 2006-2015 |
| 奇瑞 | 艾瑞泽5 | M1X | 艾瑞泽5 | 2016- |
| 荣威 | RX3 | SSARX3 | RX3 | 2017- |
| 江淮 | 同悦 | J2 | 同悦 | 2008-2014 |

### 行话翻译参考表

完整映射表见 `references/chinese-vehicle-slang-engine-translation.md`（200+条目，覆盖本田/日产/丰田/现代/大众/标致/奔驰/宝马/福特/通用/路虎/长城/奇瑞/吉利及中国自主品牌）。

### 防御性备注输出规则

每次翻译后必须在备注中写明匹配前提：
> "按 [具体年份/代数/底盘号] [发动机型号/底盘号] 匹配，不适用于 [容易混淆的其他代数/底盘]"

### 电商平台搜索策略（兜底方案）

当泰安联和 17vin 都查不到 OE 号时（常见于中国自主品牌和冷门车型），使用电商平台搜索。

**搜索策略**：
1. **淘宝** (taobao.com)：搜索 `"{车型} {配件名} OE号 原厂"` 或 `"DAC{编号} {车型}"`
2. **京东** (jd.com)：搜索 `"{车型} 轮毂轴承 原厂"` 或 `"{车型} 涨紧轮 OE"`
3. **1688** (1688.com)：搜索 `"{车型} 轴承 OEM"` 或 `"{工厂编号} 配套"`

**数据提取方法**：
- 商家通常在商品标题或详情页列出 OE 号
- 多店铺对比：至少 3 家不同店铺列出相同的 OE 号才可采纳
- 优先看有实物图的商家（实物图上的 OE 钢印更可信）
- 通过 `web_search` 获取商品标题列表，提取 OE 号关键词

**可靠性评级**：

| 来源 | 可靠度 | 说明 |
|------|--------|------|
| 多店铺一致 | ★★★ | 3+店铺统一 OE 号，可靠性高 |
| 实物图 OE 钢印 | ★★★ | 产品实物照片上的 OE 钢印 |
| 单店铺标注 | ★★ | 需谨慎，可能是商家自行标注 |
| 仅商品标题含 OE | ★ | 仅为关键词优化，不一定准确 |

**标记规则**：电商来源的 OE 号备注注明"电商平台多店铺验证"或"电商单店铺标注，待确认"。

## 输入要求

```
工厂编号：如 DAC39720037-2RZ(ABS88)
适配车型：如 福特嘉年华（11-15款）、翼博（13-16款）、马自达2两厢（07-15款）
关联编号列表（可选）：用户提供的已知关联 OE
```

**⚠️ Excel 读取注意**：沙盒 Python 环境中没有 `openpyxl`。读取 Excel 文件必须用系统 Python 通过 subprocess 调用：
```python
subprocess.run(["/home/linuxbrew/.linuxbrew/bin/python3", "-c", script], capture_output=True, text=True)
```

## 清洗流程

```
┌─────────────────────────────────────────────────────────────┐
│                   数据清洗主流程                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  预处理：行话翻译                                             │
│  - 将模糊车型描述翻译为具体车型+发动机/底盘号                   │
│  - 详见上方"车型数据清洗（行话翻译）"章节                      │
│                                                             │
│  步骤0：工厂编号解析（批量）                                   │
│  ├─ 一代轴承：DAC39720037-2RZ(ABS88) → 搜索编号: 39720037     │
│  │   格式: 内径(2)+外径(2)+变型(2)+高度(2)            │
│  └─ 二代/三代轮毂单元：RAH3177A → 无法拆解，需后台获取参数      │
│                                                             │
│  步骤0.5：轮毂单元必须先从后台获取参数                          │
│  ├─ 调用睿锋后台 API 查询产品详情                              │
│  ├─ 获取：是否带ABS、安装位置、极数/齿数、产品图片              │
│  └─ 这些参数是后续搜索的筛选条件                                │
│                                                             │
│  步骤1：泰安联 CDP 搜索（8位核心编号 / OE号）                  │
│  一代：用8位纯数字编号搜索                                      │
│  轮毂单元：用OE号或车型+配件名称搜索                            │
│                                                             │
│  步骤2：17vin EPC 查询（车型验证）— 浏览器 CDP / API 方式     │
│  所有品牌：网页端EPC查询 / 配件搜索快速路径                    │
│                                                             │
│  步骤3：电商平台搜索（泰安联+17vin 均无结果时）                 │
│  淘宝/京东/1688 交叉验证                                      │
│                                                             │
│  步骤4：交叉比对 + 输出报告                                   │
│  多来源的 OE 对比、参数对比                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 注意事项

- **分步执行**：每个模块独立运行，一个完成后确认再进入下一步
- **用户参与环节**：
  - 泰安联/TecDoc 需要用户先登录（验证码手动完成）
  - 产品图片需要用户肉眼比对
  - 不一致的 OE 号需要用户确认
- **成本控制**：17vin API 按次收费（3 分钱/次），合理使用缓存
- **优先级**：数据清洗优先处理 A 类产品（销量最高的），再逐步扩展
- **缓存策略**：查询结果应保存到本地，避免重复调用

### 批量清洗推荐流程（2026-06 经验）

对批量产品的清洗，推荐顺序：

1. **Excel 关联编号校验**（用 `data-clean cross-validate` 命令）
   ```bash
   cli-anything-platform-service data-clean cross-validate --file 文件.xlsx --check-structure
   ```
   - 输出三类：A) DAC格式轴承型号、B) 格式差异(归一化匹配)、C) 真正缺失
   - 只处理 C 类（真正缺失），A 类需确认是否应为 OE 号，B 类确认即可
   - **⚠️ 同时做结构性检查**：工厂编码是否全填、OE 列是否为真实车辆 OE 号（非 DAC/DU 轴承规格编号）
2. **泰安联 CDP 搜索**（核心验证渠道，第一步查询）
   ```bash
   cli-anything-platform-service data-clean taianlian-search --query <8位数字/OE号>
   ```
   - 一代轴承：用8位纯数字编号（去掉前缀后缀）
   - 轮毂单元：用 OE 号搜索
   - **长安品牌部分有数据**（冠盛/GSP），比亚迪/宝骏基本只有JSPT/READYGOO小品牌无参数
   - 批量操作用子agent并行 web_search，但泰安联浏览器查询必须顺序执行
   - **查完立即做位置交叉验证**：泰安联安装位置 vs Excel名称列

3. **17vin 网页端 EPC**（泰安联未命中的产品，浏览器 CDP）
   ```bash
   cli-anything-platform-service data-clean epc-query --keyword <车型>  # API 方式
   ```
   - 用户在 CloakBrowser 中登录 17vin（首次），后续持久化 profile 复用
   - CDP 连接操作网页端 EPC 查询
   - 查看关联编号中是否有 SKF、NSK、FAG 等大厂 OEM
   - ✅ 适用于所有品牌（网页端无 API 限制）
   - **⚠️ 注意：逐车 EPC 树导航每车需 3-5 分钟，对批量任务优先使用配件搜索快速路径（见下方补充）**

### 补充：17vin 配件搜索快速验证（2026-06-02 新发现）

**配件搜索比 EPC 树导航快 10 倍以上（10-30秒 vs 3-5分钟）。**

#### 三级验证法

**第一级：品牌 + 配件类型（10秒）**
```
https://www.17vin.com/partsearch/{OE号(无横杠)}.html
```
确认 OE 是否被 17vin 收录，品牌是否正确。

**第二级：配件名称 + 替换号（10秒）**
```
https://www.17vin.com/modellist/{OE}/{group_id}.html
```
查看配件名称判断是张紧器/皮带/惰轮，获取替换号列表。

**第三级：车型适配（仅部分 OE 有数据）**
页面底部"适用车型列表"显示实际适配的车型和发动机型号。

#### 17vin 品牌覆盖

| 可收录 | 不可收录 |
|--------|---------|
| ✅ 日系(丰田/本田/日产/马自达) | ❌ 德系(大众/奥迪/宝马/奔驰) |
| ✅ 韩系(现代/起亚) | ❌ 美系(福特/GM/克莱斯勒) |
| ✅ 法系(标致/雪铁龙) | ❌ 自主品牌(吉利/奇瑞/长城/北汽) |

不可收录品牌需走 EPC 浏览器导航或泰安联。

详见 `references/17vin-partsearch-fast-verify.md`。
4. **睿锋后台 API 查询**（验证产品是否已录入系统）
   ```bash
   cli-anything-platform-service data-clean backend-search --keyword <关键词> --with-details
   ```
   - 搜索 8位纯数字、OE号、DAC编号
   - `code` 字段可能为空，需同时检查 `oe` 字段
5. **标记待确认**（所有渠道都无结果的产品）
   - 直接问工厂获取 OE 号
   - 或标记"待确认"入库，后续人工补充

6. **电商平台搜索**（泰安联+17vin 均无结果的产品）
   - 淘宝/京东/1688 搜索 "{车型} {配件名} OE号"
   - 至少 3 家不同店铺列出相同 OE 号才采纳
   - 优先采信实物图 OE 钢印
   - 备注标注数据来源"电商平台交叉验证"

## ⚡ 工厂原表交叉引用

### 核心策略

报价表与工厂产品目录的交叉匹配，三通道逐级降级：

1. **睿锋后台 API 匹配**（最可靠）：通过 `data-clean backend-search` 搜索 OE 号，归一化比对（去横杠空格）
2. **OEM 号匹配工厂表**：建立 OEM 索引（归一化前 8-10 位），精确+模糊匹配
3. **品牌车型模糊匹配**（建议性）：从车型描述提取品牌关键词匹配，需人工核实

已知 OE→RAT 映射表见 `references/factory-table-cross-reference.md`。

### 关联编号 OE 校验（Excel 批量验证）

对 Excel 中的 OE 和关联编号列批量校验，归一化去横杠空格后比对：

- **DAC/DU 格式**：轴承规格编号，非车辆原厂 OE，需补充真实 OE
- **格式差异**：`517200Q000` vs `51720-0Q000`，归一化后匹配
- **真正缺失**：关联编号中完全找不到，需外部查询补全

### 归一化校验

```python
# 忽略横杠、空格、大小写的归一化比较
oe_normalized = oe.replace("-", "").replace(" ", "").upper()
related_normalized = related.replace("-", "").replace(" ", "").upper()
found_normalized = oe_normalized in related_normalized
```

### 跨目录尺寸匹配（核心8位编号匹配）

详见 `references/cross-catalog-dimension-matching.md`。

### 跨表合并 + 按包装规格汇总

当用户提供多份产品清单（如退货表、库存表、出货表）需要合并并统计包装需求时，使用以下流程：

```
┌─────────────────────────────────────────────────────────┐
│              跨表合并 + 包装规格汇总流程                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  步骤1：读取所有表，建立参照表映射                         │
│  - 精确匹配：产品编号完全一致                              │
│  - 核心8位匹配：DAC/DU 提取8位核心编号                    │
│  - 近似匹配：同内径+外径，高度差≤2mm，变型差≤8             │
│  - 前缀匹配：RAH2014A → RAH2014                         │
│                                                         │
│  步骤2：合并相同编号（数量累加，尺寸优先保留非空值）         │
│                                                         │
│  步骤3：过滤无包装尺寸的行                                │
│  - 去掉包装尺寸为空的行                                   │
│  - 保留特殊分类项（如"雷迪克外采""雷迪克外购"）             │
│                                                         │
│  步骤4：按包装规格分组                                    │
│  - Key: (内盒尺寸, 外箱尺寸, 装箱数)                      │
│  - 累加总数量，记录产品明细                               │
│  - 输出格式：内盒尺寸 | 外箱尺寸 | 装箱数 | 总数量 | 产品明细│
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**关键注意事项：**
- .xls 旧格式用 xlrd 读取（系统 Python `/usr/bin/python3`），.xlsx 用 openpyxl 写回
- WSL2 中 linuxbrew Python 和系统 Python 模块不互通，需明确指定解释器
- 特殊分类项（无尺寸但需保留）应单独记录原因
- 包装尺寸匹配 ≠ OE 兼容性验证，前者是物流需求，后者是技术需求

## Excel 内嵌图片提取

参见 `references/excel-image-extraction.md`——从产品目录 Excel 中提取内嵌图片并按产品编码命名。流程：解析 drawing XML 获取图片锚点 → 映射到产品编码列 → 保存为 `{编码}.{扩展名}`。

## 错误处理

| 错误 | 处理 |
|------|------|
| 泰安联+17vin均无结果 | 进入电商平台搜索（淘宝/京东/1688）；如仍无结果，标记"待工厂确认" |
| 电商平台搜索结果不一致 | 优先采信多店铺一致的 OE + 实物图钢印；如冲突标注"多源不一致，待工厂确认" |
| 17vin API 返回 503 | 检查 `http_proxy` 环境变量 — 代理会阻断 `api.17vin.com:8080` 的连接。设置 `no_proxy="127.0.0.1,localhost,::1"` 或在 `urllib.request` 前执行 `os.environ['no_proxy']` |
| 17vin SFH API (`openapi.sfh123.cn`) | 新 API，HMAC-SHA256 签名鉴权；`/vin/query` 可用，`/parts/query` 需 `vin`/`vehicleIds` 参数（不支持 OEM 反向查询） |
| 17vin Section 4 API（4001/4004/40031）| ✅ 实际可用！见 `references/17vin-section4-api.md`（之前误报503是因为代理环境问题） |
| 泰安联无匹配结果 | 可能是参数编码问题或 OE 号不正确，标记异常，需人工确认 |
| CDP 端点不通 | 检查调试 Chrome 是否运行，端口 9222 是否监听 |

## ⚠️ 已知坑（Pitfalls）

注: Pitfall 编号继承自历史版本，编号不连续是因为部分旧条目已在版本迭代中移除或合并。

### 27. 后台 API 搜索参数必须用 queryType=ENCODE+keyword（2026-05-15 实测）

**product/list 的正确调用方式：**
- ✅ `?queryType=ENCODE&keyword=44825037&page=1&size=20`
- ❌ `?code=44825037` — 不返回结果
- ❌ `?oe=44825037` — 不返回结果
- ❌ `?pageNum=1&pageSize=20` — 参数名不对
- ❌ 缺少 `queryType=ENCODE` — 不返回结果

**响应字段名是 `content` 不是 `records`：**
- `data.content` = 产品数组
- 不是 `data.records`（之前所有用 records 的脚本结果为空）

**`code` 字段经常为空：**
- 很多产品 `code=""`，只能通过 `oe` 字段识别
- 搜索时 keyword 匹配的是 code/oe/num 等多个字段

**productNumDetail/list 和 productParamDetail/list 返回 dict 嵌套结构：**
- 不是 list，需要遍历 dict 的 values 提取 list
- 直接 `nums[0]` 会报 KeyError

### 28. 13999999999 就是管理员账号（2026-05-15 确认）

之前误认为是"运营账号"导致 API 无权限。实际上该账号就是管理员，API 返回空数据是因为**搜索参数错误**，不是权限问题。

### 10. 泰安联搜索方式（CloakBrowser CDP Server）

**方案变更（2026-05-28）**：从 Windows Chrome CDP 改为 CloakBrowser CDP Server（隐形 Chromium，58 个 C++ 隐身补丁）。

**优势**：
- 隐身补丁阻止验证码出现（30/30 检测通过，reCAPTCHA v3 得分 0.9）
- WSL2 Docker 内闭环运行，无需跨 OS 依赖
- 持久化 profile 保存登录态，一次登录持续复用
- 每连接独立指纹，反检测

**启动 CloakBrowser CDP Server**：
```bash
docker run -d --name cloak -p 9222:9222 \
  -v ~/.cloakbrowser/profiles/taianlian:/profiles \
  cloakhq/cloakbrowser cloakserve \
  --profile-dir=/profiles \
  --fingerprint-seed=taianlian-fixed \
  --timezone=Asia/Shanghai \
  --locale=zh-CN
```

**验证连接**：
```bash
curl http://localhost:9222/json/version
```

**Hermes 连接**：`browser.cdp_url: http://localhost:9222`（在 `~/.hermes/config.yaml` 中配置）

**注意事项**：
- 首次使用需在 CloakBrowser 中手动登录泰安联（验证码），后续持久化 profile 复用登录态
- CloakBrowser 不解决验证码，但通过隐身补丁**阻止验证码出现**
- 如仍触发验证码，CLI 会提示用户手动完成
- 详见 `cloakbrowser-cli` skill 的 CDP Server 部署指南

### 11. 批量查询必须顺序执行，不可并行（2026-06 修正）

**CDP 连接同一个 Chrome 实例时，不能并行操作浏览器。**

原因：
- 同一 Chrome 实例共享浏览器状态（标签页、页面导航、ref 值）
- 多个 agent 同时操作会导致页面冲突、ref 失效、标签页切换混乱
- 之前建议的"delegate_task 分3个子agent并行"是错误的

正确做法：
- 泰安联/TecDoc/17vin 的浏览器查询必须**顺序执行**
- 单个 agent 依次处理每个产品，约 20-30 秒/产品
- 可并行的部分：web_search、宜配网查询、电商平台搜索（无状态 HTTP 请求）

### 12. 工厂编号解析格式（2026-06 修正）

工厂编号格式：`{前缀}{内径2位}{外径2位}{外径变型2位}{高度2位}{后缀}`

| 示例 | 内径 | 外径 | 变型 | 高度 | 泰安联搜索编号 |
|------|------|------|------|------|------|
| DAC34640037-2RZ | 34 | 64 | 00 | 37 | 34640037 |
| DAC42840040-2RZ(ABS96) | 42 | 84 | 00 | 40 | 42840040 |
| DAC40720836RZ/RS(ABS88) | 40 | 72 | 08 | 36 | 40720836 |
| DU407300552RZ/ABS96 | 40 | 73 | 00 | 55 | 40730055 |

注意：`高度` 是最后2位数字，不是中间的 `00`（中间00是外径变型）。

### 14. ABS 状态判断规则（2026-06 确认）

**工厂编号中没有 ABS 标识 = 不带 ABS，数据可靠。**

- 工厂编号中有 `(ABS88)`、`/ABS96` 等后缀 → 带 ABS
- 编号中没有任何 ABS 相关后缀 → 不带 ABS
- **不要**仅从 2RZ、RS 等密封后缀推断 ABS 状态（2RZ 仅表示双侧橡胶密封，与 ABS 无关）
- 泰安联/TecDoc 搜索结果中如果标注"带 ABS 传感器环"，而工厂编号无 ABS 标识 → 不匹配，排除

### 15. 参数接近但不完全匹配的处理（2026-06 确认）

**OE 验证场景**：高度接近、外径小数位相近的产品不能直接排除，需要标识出来交给工厂技术人员判断。

一代轴承对安装尺寸比较敏感，但某些情况下：
- 高度差异在 1-2mm 内 → 可能兼容（密封件压缩余量、测量公差等），标记为"高度接近待确认"
- 外径带小数位（如 74.0 vs 74.1）→ 可能兼容，标记为"外径接近待确认"
- **具体 OE 是否兼容必须由工厂技术人员确认**，助手不能自行判断

**⚠️ 包装匹配场景（例外）**：用户明确指示，**变型/高度差距不大的可以用同样规格包装**。当目的是跨表匹配包装尺寸（而非验证 OE 兼容性）时：
- 同内径+外径，高度差 ≤2mm → ✅ 用同样包装
- 同内径+外径，变型差 ≤8 → ✅ 用同样包装
- 例：DU55900055 → DU55900054（高度差1mm），DAC40720836 → DAC40720036（变型差8）均可匹配
- 详见 `references/cross-catalog-dimension-matching.md`

### 6. 工厂编号 vs 后台参数精度差异

工厂编号 `DAC39720037` 中 `39` 是整数简写，后台实际记录精确值 `38.993mm`。比对时允许 ±0.1mm 误差，不要当作不一致。

### 8. 补货计划 Excel 列语义（2026-05-14 修正）

**重要：Excel 列的表头标签与实际含义可能不一致。** 例：列名写"OE"但内容实际是关联编号列表，真正的 OE 号在"工厂型号"列。**不要仅凭表头判断，要根据列内容的格式特征识别**：OE 号多为单一编号，关联编号列常含逗号分隔的多个编号。

### 中国自主品牌 OE 查询现实（2026-06 更新）

**17vin 6108 搜索接口覆盖情况**（2026-06 实测）：
- ✅ **可用**：byd(比亚迪)、chery(奇瑞)、ford_china(福特)、mazda_yiqi(马自达)、mitsubishi(三菱)、toyota(丰田)、benz(奔驰)、porsche(保时捷)
- ❌ **不可用**：changan(长安)、suzuki(铃木)、zotye(众泰)、nissan(日产)

**泰安联**：基本不收录中国品牌专用件
**电商平台（淘宝/京东/1688）**：中国品牌配件的主要民间数据源，需多店铺交叉验证

**中国自主品牌最可靠 OE 来源**：工厂直接提供 > 17vin 网页端 EPC（浏览器 CDP）> 人工确认

### 30. 关键原则：AI知识≠实际数据源（2026-05-28，2026-06 再次确认）

**不要在 OE 匹配任务中仅靠 AI 内部训练知识替代实际数据查询。** 

**2026-06 17vin 实测发现的 AI 知识库根本性错误：**

| AI 知识库 OE | AI 判定 | 17vin 实际配件名 | 17vin 实际适配 | 严重程度 |
|-------------|--------|----------------|--------------|---------|
| 31110-RAA-A01 | 本田张紧器总成 | BELT, ALTERNATOR（发电机皮带）| R系列发动机 | 🔴 配件类型错误 |
| 11955-JA00A | 日产 MR20DE/VQ/HR16DE 通用 | 自动张紧器 | 仅 QR25DE 2.5L | 🔴 发动机泛化错误 |
| 25281-2G000 | 现代/起亚全系通用 | 张紧轮总成 | 仅 Theta-II(G4KD/G4KJ/G4KH) | 🟡 不适配 V6/柴油 |
| 16620-31070 | 丰田全系张紧器 | 多楔带张紧器总成（水泵）| 2GR-FXE 混动 V6 | 🟡 用途错误 |

**17vin 品牌覆盖实测（2026-06）：**

| 品牌集群 | 配件搜索收录 | 车型列表 |
|----------|------------|---------|
| 现代/起亚 | ✅ | ✅ 19车型 |
| 日产 | ✅ | ✅ 17车型 |
| 丰田/雷克萨斯 | ✅ | ⚠️ 0车型 |
| 本田/讴歌 | ✅ | ⚠️ 0车型 |
| 标致/雪铁龙 | ✅ | ⚠️ 0车型 |
| 马自达 | ✅ | ❌ 数据不完整 |
| VW/Audi/BMW/Merc | ❌ | ❌ |
| Ford/GM/Chrysler | ❌ | ❌ |

17vin 配件搜索 URL: `https://www.17vin.com/partsearch/{OE_no_dashes}.html`
17vin Web API 文档: `www.17vin.com/doc.html`（Section 6 为车型查全车件）
SFH 新 API: `openapi.sfh123.cn`（HMAC-SHA256，app_key 已获取，签名格式待确认）

### 30. 关键原则：AI知识≠实际数据源（续）

(接上文 #30，补充 2026-06 实测验证数据)

**不要在 OE 匹配任务中仅靠 AI 内部训练知识替代实际数据查询。**

**⚠️ 2026-06-02 强化：AI 知识库在张紧器 OE 匹配中被 17vin 实测证明存在根本性错误。** 具体案例：
- AI 将本田 `31110-RAA-A01` 识别为张紧器，17vin 确认它是**发电机皮带(BELT)**
- AI 将日产 `11955-JA00A` 映射到 MR20DE/VQ/HR16DE，17vin 确认它**仅适配 QR25DE 2.5L**
- AI 将现代 `25281-2G000` 映射到所有现代发动机，17vin 确认它**仅适配 Theta-II 系列**

**正确的验证流程：**
1. ✅ 17vin 配件搜索 → 确认配件类型（张紧器/皮带/惰轮）
2. ✅ 17vin 车型列表 → 确认具体适配发动机和车型
3. ✅ 泰安联 CDP → 交叉验证替换号
4. ✅ 配件厂商交叉引用(SKF/NSK/FAG/盖茨等) → 辅助参考（也需验证，厂商编号也可能有误）
5. ❌ AI 知识库 → **仅作初步参考，不可直接用于生产数据**

### 31. 睿锋后台API：分类搜索 categoryIds 参数 + 张紧轮OE格式差异（2026-05-28）

**分类ID查询（涨紧轮）：**
```
GET https://rfscm.com/api/principal/product/list
  ?page=1&size=100&queryType=ENCODE&categoryIds=655709386127314944&queryThird=false
```
- categoryIds=655709386127314944 是"涨紧轮"分类，返回 668 条
- keyword 搜索只返回 44-50 条（文本匹配不足）
- 惰轮/过渡轮 关键词在后台查询结果为 0，需搜索"涨紧轮"或"张紧器"
- 后台产品 code 以 RAT 开头（如 RAT2801、RAT2680、RAT2460）

| AI知识库中的OE | 后台实际存OE | 差异原因 |
|---------------|-------------|---------|
| 06B903315A | 06B903341B | 315=总成，341=液压缸 |
| 25281-2B000 | 252812B020 | 格式差异（无横杠） |
| 11955-JA00A | 11955JD21A | 尾缀差异 |

### 32. 睿锋后台API：WSL DNS + Token 字段 + OE格式差异（2026-05-28）

**WSL 中 rfscm.com DNS 解析失败：**
```python
# ✅ IP直连 + Host头
BASE = "https://8.155.164.3"
session.headers["Host"] = "rfscm.com"
session.verify = False
# ❌ 直接域名（WSL DNS不解析）
BASE = "https://rfscm.com"  # 会 SSL.HANDSHAKE_FAILURE
```

**Login 响应字段不是 `access_token`：**
```python
# ✅ 正确字段名
token = r.json()["data"]["token"]
# ❌ 错误字段名
token = r.json()["data"]["access_token"]  # KeyError
```

**登录API结构：**
```json
{"code": 200, "msg": "操作成功", "status": true, "data": {
    "token": "eyJhbG...", "userId": "...", "nickName": "运营"
}}
```

**OE 号在后台存为无横杠格式：**
```python
# 搜索时需要归一化
search_key = oe.replace("-", "").replace(" ", "")
# 例: "25281-2B000" → "252812B000" 才能匹配后台的 "252812B020"
# 精确匹配很难，建议先精确搜，再模糊搜（用前5-8位）
```

**后台张紧器类产品搜索：**
- 关键词"张紧器"→ 44条（总成类）
- 关键词"张紧轮"→ 50条（含自动张紧轮、皮带张紧轮等）
- 关键词"惰轮"→ 0条（后台不使用该术语）
- 关键词"过渡轮"→ 0条
- 产品 code 值以 RAT 开头（如 RAT2801、RAT2680），可从 oe 字段推断对应车型

### 33. http_proxy 环境变量阻断 17vin API 连接（2026-05-28 发现）

WSL2 终端中如果设置了 `http_proxy`（如 Clash/V2Ray 代理 `http://127.0.0.1:10808`），所有对 `api.17vin.com:8080` 的请求会通过代理转发，导致：
- Section 4 API（4001/4004/40031）返回 503
- Section 6 API（6001/6003）也可能不稳定
- API 无法正常连接

**解决方案**：在脚本中强制设置 `no_proxy` 环境变量：
```python
import os
os.environ['no_proxy'] = '127.0.0.1,localhost,::1'
```
必须在首次 `urllib.request` 调用前设置。

**execute_code 工具不受影响**（沙盒环境无 http_proxy），但 terminal 工具会继承 shell 的 http_proxy 环境变量。

### 35. 17vin Token 参数陷阱 + 批量限流（2026-05-29 实测）

**Token 生成时 `params` 绝对不能包含 `&user=`**：
```python
# ✅ 正确：params = "/?action=brands"
#     URL = BASE + params + "&user=xxx&token=yyy"
# ❌ 错误：params = "/?action=brands&user=xxx" → token 不匹配 → code 1002
```

**批量查询触发 503 限流的处理**：
```python
def call_api(params, retries=3):
    for attempt in range(retries):
        try:
            ...
            if data.get('code') == 503:
                time.sleep(5 * (attempt + 1))  # 5s, 10s, 15s
                continue
        except urllib.error.HTTPError as e:
            if e.code == 503:
                time.sleep(5 * (attempt + 1))
                continue
```
行间延迟 ≥ 2 秒，目录遍历内部 ≥ 0.8 秒。

**EPC 目录遍历注意事项**：
- 本田：cata2 直接是叶子节点，`last_cata_code_level=2`
- 配件 OE 在 `partnumber` 字段（非 `part_standard_no`）
- 张紧器关键词不同于轮毂轴承：`张紧` `涨紧` `tension` `惰轮` `idler`

**批量脚本**：`/home/stoic16/scripts/17vin_tensioner_batch.py`
（从 Excel 批量查 EPC，含 100+ 车型映射、SQLite 缓存、503 重试）

**CDP WebSocket 连接同理**：需显式设置 `http_proxy_host=""` 和 `http_proxy_port=None`：
```python
ws = websocket.create_connection(url, timeout=10, http_proxy_host="", http_proxy_port=None)
```

### 34. CDP WebSocket 连接浏览器（2026-05-28）

通过 CloakBrowser/Windows Chrome CDP 调试端口连接时：

**浏览器端**（Windows PowerShell）：
```powershell
Start-Process 'C:\Program Files\Google\Chrome\Application\chrome.exe' -ArgumentList @(
    '--remote-debugging-port=9250',
    '--remote-allow-origins=*',  # Chrome 148+ 必需
    '--user-data-dir=C:\ChromeDebugProfile',
    '--no-first-run',
    '--no-default-browser-check'
)
```

**Python 连接**（WSL2）：
```python
import websocket
ws = websocket.create_connection(page_ws_url, timeout=10, http_proxy_host="", http_proxy_port=None)
```

注意：
- `--remote-allow-origins=*` 在 Chrome 148+ 是必需的，否则 WebSocket 握手返回 403
- CloakBrowser Docker 版可能在端口 9222，但 Windows Chrome 也在 9222 时会冲突
- CDP 连续查询 400+ 次后连接可能断开（Chrome 崩溃或 session 超时），需要重新连接
- 泰安联会话可能因大量查询触发验证页面，需用户重新登录

**openpyxl 不支持 .xls 旧格式**，需要 `xlrd` 库。但 WSL2 中存在 Python 环境不一致问题：

- `pip install xlrd` 安装在系统 Python (`/usr/bin/python3`, 3.12)
- 沙盒执行代码使用的是 linuxbrew Python (`/home/linuxbrew/.linuxbrew/bin/python3`, 3.14)
- 两者模块不互通

**解决方法**：
```python
# 明确使用系统 Python 执行 .xls 读取脚本
subprocess.run(["/usr/bin/python3", "script.py"], capture_output=True, text=True)
```

**或者**：安装 xlrd 到 linuxbrew Python：
```bash
pip install --break-system-packages xlrd
# 注意：linuxbrew Python 也需要 --break-system-packages
```

**更优方案**：如果后续需要写回 `.xlsx`，建议先用 `/usr/bin/python3` + xlrd 读取 .xls 内容，再用沙盒环境（有 openpyxl）处理和输出。
