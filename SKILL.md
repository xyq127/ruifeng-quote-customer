---
name: 睿锋-客户询价
description: "【客户版·面向客户，只展示售价 salePrice，绝不输出采购价/P1/P2/P3，区别于输出全价的内部版】睿锋-客户询价：汽车配件 OE/工厂编号(DAC/DU/RAH)/尺寸/车型配件/客户报价单 → 多源查询+交叉验证 → 命中睿锋后台后只补售价 salePrice。当面向客户做询价、对外报价、查某编号或车型配件的售价、给客户报价单批量匹配售价时使用，即使没明说『客户询价』也应触发。只读，不回写后台。遵循 Plan→Execute→Verify：数据源优先级 泰安联≈17vin > 睿锋后台 > 电商(需3家店铺一致)；编号选取 主机大厂OE > 大厂关联编号(SKF/NSK/FAG) > 其他小厂。"
version: 3.1.0
author: Hermes Agent
category: quote-customer
changelog: |
  3.1.0 (2026-06-25): 客户版重定位 — 从「数据治理」收敛为「客户询价（只读+只报售价）」；移除全部回写/治理内容（num-save/param-save/cross-validate、置信度的可回写措辞）；精简依赖段与重复表格
  3.0.0 (2026-06-17): 架构重构 — Plan→Execute→Verify 循环框架；CLI 拆分为独立仓库 cli-anything-platform-service；新增 workflows/ 目录定义核心工作流；项目更名为「睿锋数据治理」
  2.2.0 (2026-06-15): 跨平台改造（自管 Chrome + Python 环境自动检测）；新增 CDP 连接与登录引导流程；新增子技能"快速OE查询"
  2.1.0 (2026-06-13): 新增产品报价核心链路 quote-match；地基改进：backend-search 归一化多轮重试链
  2.0.x (2026-06-04~12): 初始版本 — 工厂编号解析、OE交叉验证、多源查询、参数回写
depends_on:
  - 工厂编号解析
  - 17vin-EPC查询
  - 泰安联TecDoc搜索
  - 快速OE查询
---

# 睿锋-客户询价

## 概述

面向**客户**的汽车配件询价技能：对客户给出的编号 / OE / 尺寸 / 车型配件 / 报价单做**查询 → 多源交叉验证 → 输出含售价的报价**。核心目标是确认"工厂编号 ↔ OE ↔ 车型"三位一体映射准确，并给出可信的**售价（salePrice）**。

> **这是只读的客户版**：只对客户暴露售价 `salePrice`，**绝不输出采购价 / P1 / P2 / P3**，也**不回写后台**（写关联编号/参数、交叉验证回写属内部版职责，本版不做）。需要看全价或回写时请用内部版「睿锋-内部询价」。

## 首次配置（每用户一次）

每个用户首次使用前，跑一次配置向导，把**所有个人凭据集中录入一份个人配置文件**——睿锋登录手机号+密码、17vin 用户名+密码一处搞定（客户版**无需任何图片识别 Key**，图片由 Agent 自身视觉直接读取）：

```bash
python scripts/personal_config.py init     # 交互式录入（密码用 getpass，不进命令行历史）
python scripts/personal_config.py show      # 查看状态（密码/Key 自动打码）
```

- **存储位置**：`~/.cli-anything-platform-service/config.json`（权限 `0o600` 仅本人可读；`RUIFENG_CONFIG` 可改路径）。与睿锋/17vin 自包含模块、RayForm-CLI **共用同一文件**，token 互通。
- **不随 skill 分发**：该文件在用户 `$HOME` 下，`npm install` 重装 skill **不会覆盖或读取它**；仓库内只有无密钥的模板 `scripts/config.example.json` 供参考。
- 所有自包含脚本（`ruifeng_platform.py` / `vin17_epc.py`）都从这份配置读凭据；环境变量（`17VIN_*`、`PLATFORM_*`）始终可临时覆盖。

### 首次运行检测（Agent 必读，执行任何查询前先做）

**Agent 在执行任何查询/识别前，先检测个人配置是否就绪：**

```bash
python scripts/personal_config.py check                 # 全部功能；退出码 0=就绪, 2=首次运行/缺项
python scripts/personal_config.py check --feature ruifeng  # 只查睿锋登录（按本次任务需要）
```

- **退出码 0** → 配置就绪，正常执行。
- **退出码 2（首次运行 / 缺项）→ 不要尝试查询。** 把脚本输出的「缺少项」清单**转达给用户**，并请用户**在自己的终端**运行 `python scripts/personal_config.py init` 录入这些信息。
  - 密码用 `getpass` 安全输入，**不要让用户把密码发给 Agent**，也不要由 Agent 代填（避免进入对话/命令行历史）。
  - 用户也可临时用环境变量提供（`17VIN_*` / `PLATFORM_*`）。
  - 配置完成后再继续原任务。

> 任一自包含脚本在凭据缺失时也会自行打印同样的首次运行提示并非零退出——Agent 看到该提示即按上述方式引导用户，不要反复重试。

## 依赖

绝大多数询价只需 **Python3 + requests** 的两个自包含脚本，**无需安装 CLI**：

- **睿锋平台（`scripts/ruifeng_platform.py`）：** 登录、后台搜索、产品详情、售价查询。
  ```bash
  python scripts/ruifeng_platform.py config-use prod          # 选环境
  python scripts/ruifeng_platform.py login --mobile <手机号>   # 密码交互输入，token 落盘
  python scripts/ruifeng_platform.py price --keyword 90363-45050 --json  # 售价 salePrice
  ```
  **登录态自愈**：查询遇 401/403 或 `body.code=401`/`status=false` 且消息含「登录/token/失效/过期」时，自动用已存凭据重登一次并重试，新 token 落盘，无需人工介入（需 `login` 时落盘密码；`--no-save-password` 可不落盘，失效则需手动重登）。
- **17vin EPC（`scripts/vin17_epc.py`）：** OE 互换 / 大厂关联件 / 适配车型，纯 HTTP。
  ```bash
  python scripts/vin17_epc.py config-set --username <用户名>   # 密码交互输入
  python scripts/vin17_epc.py oe --oe 31110-RAA-A01 --json     # 互换OE/品牌件/车型(三步链)
  ```
  确保 `no_proxy` 包含 `api.17vin.com`。

凭据统一存 `~/.cli-anything-platform-service/config.json`（`0o600`，与 RayForm-CLI / 内部版共用，token 互通），**不在分发的 skill 里硬编码账号**；环境变量（`PLATFORM_*` / `17VIN_*`）始终可临时覆盖。

- **CLI 工具（可选，仅重流程需要）：** `cli-anything-platform-service` 仅用于泰安联浏览器搜索(`taianlian-search`，CDP)、报价匹配(`quote match`)等。`pip install -e /path/to/cli-anything-platform-service[data-clean]`
- **Chrome CDP：** 仅泰安联 TecDoc 搜索需要调试端口 9250（17vin 已改自包含 HTTP，不再需要）。

---

## Plan → Execute → Verify 框架

Agent 执行客户询价任务时，严格遵循以下循环：

```
用户输入 → PLAN（识别+匹配工作流） → EXECUTE（按工作流执行） → VERIFY（校验结果）
                                                                    │
                                                    通过 ←──────────┘
                                                      │
                                                    不通过 → 标记问题 → 回到 PLAN
```

### 1. Plan（输入识别 + 匹配工作流）

首先识别用户输入的类型，然后匹配对应工作流：

| 输入类型 | 示例 | 匹配工作流 |
|---------|------|-----------|
| 工厂编号 (DAC/DU/RAH) | `DAC39720037` | [oe-lookup](workflows/oe-lookup.md) |
| 尺寸规格 | `45x84x45` | [oe-lookup](workflows/oe-lookup.md) |
| OE/关联编号 | `31110-RAA-A01` | [oe-lookup](workflows/oe-lookup.md) |
| 车型+配件名 | `本田雅阁2.4L 涨紧轮` | [oe-lookup](workflows/oe-lookup.md) |
| 客户报价单 (Excel) | `报价单.xlsx` | [quote-match](workflows/quote-match.md) |
| 纯文本编号列表 | `DAC39720037, 45840045` | 按行拆分为多个 oe-lookup |
| **图片**（轴承钢印照/包装盒/报价单截图等） | `bearing.jpg` / `quote.png` | **先经「图片输入预处理」读出编号/OE，再按识别结果路由到上表对应工作流** |

如输入类型无法识别，询问用户明确。

#### 图片输入预处理（读图 → 编号 → 再查询）

当输入是**图片格式**（`.jpg/.jpeg/.png/.webp/.bmp` 文件路径或图片 URL）时，**不可直接进入查询工作流**，必须先把图片里的编号/OE/钢印文字读出来，拿到文本编号后再回到上面的输入类型表正常路由。

> **客户版简化：Agent 直接用自身视觉读图，零配置、无需任何 Key。** 用 Read 工具打开图片路径即可看到内容，无需调用外部识别脚本或 SiliconFlow API。本地图片直接传路径；图片 URL 先下载到本地再用 Read 打开。

读图要点：
1. **识别优先级**：实物钢印 OE > 包装盒印刷编号 > 截图文字。多个候选时全部列出，交由后续工作流按「编号选取优先级」（主机大厂 OE > 大厂关联编号 > 小厂）取舍。
2. **拿到编号后**：把读出的编号当作普通文本输入，按输入类型表重新判定（DAC→oe-lookup、OE→oe-lookup、报价单截图的多行→逐行拆分为多个 oe-lookup），执行后续多源查询/价格补充。
3. **必须复述识别结果让用户确认**再继续查询——视觉读图可能误读字符（0/O、8/B、5/S），错号会污染整条链路。
4. **失败处理**：图片全模糊/无编号 → 请用户提供更清晰的图或直接给文本编号，不强行查询。

### 2. Execute（执行工作流）

读取匹配的工作流文件（`workflows/*.md`），按其定义的步骤逐步执行。每条工作流定义了：
- 触发条件
- Plan 阶段输入识别规则
- Execute 阶段每步的 CLI 命令、输入输出 schema、失败处理
- Verify 阶段的校验规则和置信度分级

### 3. Verify（数据校验）

执行完成后进入校验阶段：
- 按工作流定义的校验规则比对多源结果
- 输出置信度标签（A/B/C/D）
- 通过 → 输出最终结果
- 不通过 → 标记具体问题，回到 Plan 阶段制定修正策略（如切换数据源、降级到电商搜索、标记待工厂确认）

---

## 工作流索引

| 工作流 | 文件 | 适用场景 |
|--------|------|---------|
| **OE 查询** | [workflows/oe-lookup.md](workflows/oe-lookup.md) | 单个 OE/工厂编号/尺寸/车型 → 多源查询+校验 |
| **报价匹配** | [workflows/quote-match.md](workflows/quote-match.md) | 客户报价清单 → 批量报价+三方补查 → 4-sheet Excel |
| 车型行话翻译 | 参考库 | `references/chinese-vehicle-slang-engine-translation.md` |

---

## 关键规则

以下为执行过程中容易出错的硬约束：

### 1. 后台搜索必须用 queryType=ENCODE

CLI 已内置此参数。响应字段为 `data.content`（不是 `records`）。分类搜索用 `categoryIds` 参数，涨紧轮分类 ID: `655709386127314944`。

### 2. 一代轴承泰安联 DAC 编码格式

格式：`{内径:02d}{外径:02d}00{高度:02d}`。例如 45×84×45 → `45840045`。用 `data-clean oe-query --query <编码>` 一步完成。

### 3. 工厂编号解析顺序

格式：`{前缀}{内径2位}{外径2位}{变型2位}{高度2位}{后缀}`。例 `DAC39720037` → 内径39, 外径72, **变型00**, 高度37。中间 `00` 是外径变型，不是高度！

### 4. CDP 必须顺序执行

Chrome 实例共享浏览器状态，并行操作导致页面冲突。泰安联/17vin 浏览器查询严格顺序执行。无状态 HTTP 请求可并行。

### 5. 17vin 品牌覆盖

配件搜索收录：日系(丰田/本田/日产/马自达) ✅、韩系(现代/起亚) ✅、法系(标致/雪铁龙) ✅。
不可收录：德系(大众/奥迪/宝马/奔驰)、美系(福特/GM)、中国自主品牌。不可收录品牌需走 EPC 浏览器导航或泰安联。

### 6. 切忌用 AI 知识替代实际数据查询

AI 训练知识在 OE 匹配中存在根本性错误（配件类型错误、发动机泛化错误）。正确流程：17vin 确认配件类型 → 车型列表确认适配 → 泰安联交叉验证。AI 知识仅作初步参考。

### 7. 电商平台验证规则

至少 3 家不同店铺列出相同 OE 号才可采纳。优先实物图 OE 钢印。冲突时标注"多源不一致，待工厂确认"。

### 8. 参数接近不排除

高度差异 1-2mm、外径小数位相近的产品标记"接近待确认"，由工厂技术人员判断。**OE 兼容性必须由工厂确认，AI 不能自行判断。**

### 9. Excel 列识别不要信表头

列名写"OE"但内容实际是关联编号、真正的 OE 在"工厂型号"列的情况常见。按内容格式特征识别，不依赖表头。

### 10. 防御性备注

每次车型翻译后必须备注匹配前提："按 [具体年份/底盘号] [发动机] 匹配，不适用于 [易混淆的其他代数]"

### 11. 命中睿锋平台数据必须补充售价（客户版）

> **客户版 skill：只对客户暴露售价 `salePrice`，不输出采购价 / P1 / P2 / P3。**

凡查询命中睿锋后台产品，输出必须带 **售价（salePrice）**，走 **`/inventory/list`**（`keyword`=编号/OE + `queryType=ENCODE`，取 `data.content[].salePrice`）。统一用 `scripts/product_price_query.py --keyword <编号/OE>` 查询。oe-lookup 与 quote-match 均只补这一个售价列。价格为空显示 `—`，不阻断流程。

### 12. 睿锋后台多产品优先级排序

当睿锋后台查询返回多个产品时，按以下优先级排序展示：

1. **status=1** 的产品排在前面（status 非 1 的排后面）
2. 同一 status 内，按 **targetPndSource**（数组）排序：**空数组（直接 OE 匹配）> 含 1 > 含 2（无1）> 仅含 0**

即最终排序：status=1 + targetPndSource 空 → status=1 + 含 1 → status=1 + 含 2 → status=1 + 仅 0 → 非1 + 空 → …

Agent 展示多个产品时遵循此顺序，最优匹配的产品排在最前面。

---

## 数据源优先级

| 优先级 | 数据源 | 查询方式 |
|--------|--------|---------|
| 1 | 泰安联 TecDoc | Chrome CDP 浏览器搜索 (`data-clean oe-query` 或 `taianlian-search`) |
| 1 | 17vin EPC | HTTP API + 配件搜索网页 (`data-clean oe-query` 或 `epc-query`) |
| 2 | 睿锋后台 API | `data-clean backend-search --keyword <关键词>` |
| 3 | 电商平台 | 淘宝/1688/京东，至少 3 家店铺一致才采纳 |

泰安联 ≈ 17vin 同级。同一 OE 在两者都能查到同一车型时，数据可信度最高。

## 编号选取优先级

| 优先级 | 编号来源 | 示例品牌 |
|--------|---------|---------|
| 1 | 主机大厂 OE（零件设计者） | 丰田/本田/日产/大众/奔驰/宝马/现代/福特 |
| 2 | 关联编号大厂（给主机厂代工） | SKF/NSK/FAG/冠盛/盖茨 |
| 3 | 其他小厂 | 识别度低，仅辅助参考 |

---

## CDP 连接与登录

Agent 执行任何需要泰安联 TecDoc 的操作前，需确认 CDP 连接和登录态：

1. **检测 CDP：** `GET http://127.0.0.1:9250/json/version`
2. **不可达** → 自动尝试启动 Chrome（CLI 已内置 `launch_persistent_context`）
3. **打开** `https://www.tecalliance.cn` 检测登录态
4. **未登录** → 引导用户在浏览器窗口登录，等待确认后继续
5. **浏览器 profile** 持久化到 `~/.claude/browser-data/ruifeng-chrome/`，后续会话无需重复登录

---

## 置信度体系（内部校验用，不输出给客户）

所有工作流统一使用四级置信度（仅供 Agent 内部判断，**严禁在客户回复中输出置信度标识行**，如「🟢 置信度 A — 确认」等）：

| 等级 | 标签 | 条件 | 报价建议 |
|------|------|------|-----------|
| **A** | 确认 | 泰安联+17vin+后台三者一致 | 可直接报价 |
| **B** | 较可信 | 两源一致 | 可报价，建议内部复核一眼 |
| **C** | 待确认 | 仅单源命中或源间不一致 | 报价须注明"待确认"，建议工厂核实后再正式发出 |
| **D** | 兜底 | 全部未命中 | 暂无法报价，需工厂提供 |

---

## 错误处理

| 错误 | 处理 |
|------|------|
| 泰安联+17vin 均无结果 | 走电商平台；仍无结果标记"待工厂确认" |
| 17vin API 返回 503 | 检查 `no_proxy` — 代理会阻断 `api.17vin.com:8080` |
| CDP 9250 不通 | 检查 Chrome 调试端口，或自动尝试启动 |
| 电商结果不一致 | 多店铺一致的 + 实物图钢印优先；冲突标注"待工厂确认" |
| 后台搜索无结果 | 标记"需补充"继续，不阻断后续 |

---

## CLI 命令速查

客户询价用到的命令（由 `cli-anything-platform-service` 提供；**均为只读查询，不含回写**）：

| 操作 | 命令 |
|------|------|
| 工厂编号解析 | `data-clean parse <编号>` |
| 一站式 OE 查询 | `data-clean oe-query --query <尺寸/DAC/OE>` |
| 后台产品搜索 | `data-clean backend-search --keyword <关键词>` |
| 后台产品详情 | `data-clean backend-detail --product-id <ID>` |
| 17vin EPC 查询 | `data-clean epc-query --keyword <车型>` |
| 泰安联搜索 | `data-clean taianlian-search --query <编号>` |
| 报价匹配 | `data-clean quote match --file <客户表>` |
| 售价查询(salePrice) | `python scripts/product_price_query.py --keyword <编号/OE> --json` |

> 回写类命令（写关联编号 / 写参数 / 批量交叉验证）属内部版职责，客户版**不提供、不调用**。

### 自包含命令（无需 CLI，`scripts/ruifeng_platform.py`）

| 操作 | 命令 |
|------|------|
| 选择环境 | `python scripts/ruifeng_platform.py config-use <test\|prod>` |
| 登录(token落盘) | `python scripts/ruifeng_platform.py login --mobile <手机号>` |
| 查看配置 | `python scripts/ruifeng_platform.py config-show` |
| 后台产品搜索 | `python scripts/ruifeng_platform.py search --keyword <关键词> --json` |
| 产品详情 | `python scripts/ruifeng_platform.py product --product-id <ID>` |
| 售价查询(salePrice/inventory) | `python scripts/ruifeng_platform.py price --keyword <编号/OE> --json` |

### 自包含命令（无需 CLI，`scripts/vin17_epc.py`，17vin 纯 HTTP）

| 操作 | 命令 |
|------|------|
| 配置凭据 | `python scripts/vin17_epc.py config-set --username <用户名>` |
| 查看凭据状态 | `python scripts/vin17_epc.py config-show` |
| OE 互换/品牌件/车型 | `python scripts/vin17_epc.py oe --oe <OE号> --json` |
| OE 反查配件 | `python scripts/vin17_epc.py parts --oe <OE号> --json` |
| 车型关键词搜索 | `python scripts/vin17_epc.py vehicle --keyword <车型> --json` |

所有命令支持 `--json` 输出。认证：`config login` 登录获取 token。

---

## 子技能索引

| 子技能 | 文件 | 用途 |
|--------|------|------|
| 工厂编号解析 | `modules/01-工厂编号解析/SKILL.md` | 解析 DAC/DU/RAH 格式 |
| 17vin-EPC查询 | `modules/02-17vin-EPC查询/SKILL.md` | 17vin API + 网页端查询 |
| 泰安联TecDoc搜索 | `modules/04-泰安联TecDoc搜索/SKILL.md` | 浏览器 CDP 搜索 TecDoc |
| 快速OE查询 | `modules/05-快速OE查询/SKILL.md` | 一键 OE 查询（CLI 优先） |

---

## 参考文件

| 文件 | 用途 |
|------|------|
| `references/chinese-vehicle-slang-engine-translation.md` | 车型行话 → 发动机型号 + OE 号 (200+条目) |
| `references/17vin-section4-api.md` | 17vin Section 4/6 API 完整参考 |
| `references/17vin-web-navigation.md` | 17vin Web 界面导航 + CDP 操作技巧 |
| `references/17vin-partsearch-fast-verify.md` | 17vin 配件搜索快速验证方法 |
| `references/cross-catalog-dimension-matching.md` | 跨目录尺寸匹配规则 |
| `references/product-category-code-patterns.md` | 产品分类编号规律 — 一代/二三代对照表 |
| `references/excel-image-extraction.md` | Excel 内嵌图片提取规范 |
| `references/architecture-spec.md` | 系统架构说明 |
