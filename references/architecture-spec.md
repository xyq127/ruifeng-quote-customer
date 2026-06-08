# 睿锋数据清洗系统架构 Spec

> 版本: 2.0.0 | 日期: 2026-05-28 | 状态: 设计中

## 1. 系统全景图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         用户 / Hermes Agent                          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
                ▼              ▼              ▼
┌───────────────────┐ ┌──────────────┐ ┌──────────────────────┐
│ ruifeng-data-     │ │ cloakbrowser │ │ cli-anything-        │
│ cleaning skill    │ │ -cli skill   │ │ platform-service CLI │
│ (Hermes 主技能)   │ │ (参考文档)    │ │ (Python CLI 工具)     │
├───────────────────┤ ├──────────────┤ ├──────────────────────┤
│ 工作流编排        │ │ CDP 部署指南  │ │ data-clean 命令组    │
│ 数据源选择        │ │ Python API   │ │  - parse             │
│ 错误处理策略      │ │ Profile 管理  │ │  - backend-search    │
│ CLI 命令映射      │ │              │ │  - epc-query         │
└────────┬──────────┘ └──────────────┘ │  - taianlian-search  │
         │                             │  - cross-validate    │
         │ 引用                         │  - excel-process     │
         └─────────────────────────────►│                      │
                                       └──────────┬───────────┘
                                                  │
                    ┌─────────────────────────────┼─────────────────┐
                    │                             │                 │
                    ▼                             ▼                 ▼
┌───────────────────────┐    ┌───────────────────────┐    ┌─────────────────┐
│  CloakBrowser CDP     │    │  外部 API              │    │  文件系统        │
│  Server (Docker)      │    │                       │    │                 │
├───────────────────────┤    ├───────────────────────┤    ├─────────────────┤
│ localhost:9222        │    │ rfscm.com REST API    │    │ Excel .xlsx/.xls │
│ 隐形 Chromium         │    │ api.17vin.com:8080    │    │ CSV 输出         │
│ 58 C++ 隐身补丁       │    │ 电商平台 (淘宝/京东/1688) │    │ Profile 持久化   │
│ 随机指纹 + 人化交互    │    │ tecalliance.cn (CDP)  │    │                  │
└───────────────────────┘    └───────────────────────┘    └─────────────────┘
```

## 2. 组件说明

### 2.1 CloakBrowser CDP Server

**职责**: 提供隐形浏览器实例，替代裸 Chrome 进行反检测浏览器自动化。

**部署**: WSL2 Docker，端口 9222

**关键能力**:
- 58 个 C++ 源码级隐身补丁 (navigator.webdriver=false, TLS 指纹=真实 Chrome)
- 每连接独立随机指纹，seed 固定可复现
- 人化交互: Bezier 鼠标、变速键盘、物理滚动
- 持久化 profile: 登录态跨会话保存

**配置示例**:
```bash
docker run -d --name cloak -p 9222:9222 \
  -v ~/.cloakbrowser/profiles:/profiles \
  cloakhq/cloakbrowser cloakserve \
  --profile-dir=/profiles \
  --fingerprint-seed=ruifeng-data-cleaning \
  --timezone=Asia/Shanghai --locale=zh-CN
```

### 2.2 cli-anything-platform-service (data-clean 命令组)

**职责**: 提供标准化的数据清洗 CLI 操作，封装浏览器自动化、API 调用、文件处理。

**位置**: `/home/stoic16/web-project/backend-code-repo/agent-harness/`

**命令结构**:
```
data-clean
├── parse              # 工厂编号解析
├── backend-search     # 后台 API 产品搜索
├── backend-detail     # 后台 API 产品详情(关联编号+参数)
├── epc-query          # 17vin EPC 查询
├── taianlian-search   # 泰安联 TecDoc 搜索 (CDP)
├── tecdoc-search      # TecDoc 通用搜索 (CDP)
├── cross-validate     # OE 交叉验证
└── excel-process      # Excel 处理 (read/images/cross-table-merge)
```

### 2.3 ruifeng-data-cleaning Skill

**职责**: Hermes 主技能，编排完整数据清洗工作流。

**位置**: `~/.hermes/skills/ruifeng-data-cleaning/SKILL.md`

**依赖**: cloakbrowser-cli, cli-anything-platform-service, 以及 4 个原有模块

### 2.4 cloakbrowser-cli Skill

**职责**: CloakBrowser 使用参考文档，仿 playwright-cli 模式。

**位置**: `~/.hermes/skills/browser-automation/cloakbrowser-cli/`

**文件**:
- `SKILL.md` — 主参考
- `references/cdp-server-setup.md` — 部署指南
- `references/python-api.md` — Python API
- `references/persistent-profiles.md` — Profile 管理

### 2.5 外部数据源

| 数据源 | 访问方式 | 用途 | 覆盖率 |
|--------|---------|------|--------|
| rfscm.com | REST API (Bearer Token) | 内部产品库查询 | 已录入产品 |
| api.17vin.com:8080 | REST API (MD5 Token) | EPC 目录查询 | 欧美日系品牌 |
| www.17vin.com | CDP 浏览器 | 网页端 EPC | 全部品牌 |
| tecalliance.cn | CDP 浏览器 | TecDoc 搜索 | 国际品牌为主 |
| yiparts.com | CDP 浏览器 | 辅助验证 | 中国品牌补充 |
| taobao.com/jd.com/1688.com | web_search 抓取 | OE 兜底验证 | 中国品牌及冷门车型 |

## 3. 数据流

```
Excel 文件 (工厂编号 + 车型 + 关联编号)
    │
    ▼
┌─────────────────────────────────────────────┐
│ 步骤 0: data-clean parse                    │
│ DAC39720037-2RZ(ABS88) → 内39/外72/高37    │
│ 提取 8位核心编号: 39720037                   │
│ 判断产品类型: 一代轴承 / 轮毂单元             │
└─────────────────┬───────────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
    ▼             ▼             ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐
│步骤 1    │ │步骤 2    │ │步骤 3        │
│backend-  │ │taianlian │ │epc-query     │
│search    │ │-search   │ │              │
│          │ │          │ │              │
│rfscm.com │ │TecDoc    │ │17vin EPC     │
│产品库    │ │(CDP)     │ │(API + CDP)   │
└────┬─────┘ └────┬─────┘ └──────┬───────┘
     │            │              │
     └────────────┼──────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ 步骤 4: data-clean cross-validate           │
│ 多源 OE 交叉比对                             │
│ A类: DAC格式 / B类: 归一化匹配 / C类: 缺失   │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ 输出: data-clean excel-process              │
│ 清洗后 Excel + 置信度 + 防御性备注             │
└─────────────────────────────────────────────┘
```

## 4. 浏览器架构

### 4.1 迁移路径

```
Before (当前):                       After (目标):
Windows Chrome                      CloakBrowser CDP Server
--remote-debugging-port=9250        Docker on WSL2, port 9222
--user-data-dir=C:\ChromeDebug      --profile-dir=/profiles (持久化)
                                    --fingerprint-seed=... (隐身)
                                    
Hermes browser_* tools              Hermes browser_* tools
  → http://127.0.0.1:9250             → http://localhost:9222
  
npx agent-browser                   npx agent-browser
  --cdp ws://127.0.0.1:9250/...      --cdp ws://localhost:9222/...
```

### 4.2 登录工作流

```
首次使用 (一次性):
  1. 启动 CloakBrowser CDP Server (有头模式)
  2. Hermes browser_navigate 到 tecalliance.cn/cn/login
  3. 用户手动输入账号密码 + 完成验证码
  4. 登录态自动保存到持久化 profile

后续使用:
  1. 启动 CloakBrowser CDP Server (可复用已有 profile)
  2. 直接操作，无需登录
  3. 隐身补丁避免触发新的验证码
```

### 4.3 降级策略

| 场景 | 策略 |
|------|------|
| Docker 不可用 | `python -m cloakbrowser install` 安装原生二进制 |
| CloakBrowser 不可用 | 回退 Windows Chrome CDP (原方案) |
| 验证码仍触发 | 提示用户手动完成，检查 profile 是否过期 |
| CDP 超时 | 重试 3 次，间隔 5s，仍失败则跳过该产品 |

## 5. 配置参考

### 5.1 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CLOAKBROWSER_CDP_URL` | `http://localhost:9222` | CloakBrowser CDP 端点 |
| `PLATFORM_BASE_URL` | `https://rfscm.com` | 睿锋后台 API |
| `PLATFORM_TOKEN` | — | 后台 API Bearer Token |
| `PLATFORM_ENV` | — | 环境 (test/prod) |
| `CLOAKBROWSER_CACHE_DIR` | `~/.cloakbrowser` | 二进制缓存目录 |

### 5.2 Hermes Config (~/.hermes/config.yaml)

```yaml
browser:
  cdp_url: http://localhost:9222   # CloakBrowser CDP Server
```

### 5.3 CLI Config (~/.cli-anything-platform-service/config.json)

```json
{
  "base_url": "https://rfscm.com",
  "token": "***",
  "env": "test"
}
```

## 6. 错误处理

### 6.1 CLI 层面

| 错误 | 处理 |
|------|------|
| 后台 API 401 | 提示 token 过期，引导重新登录 |
| 后台 API 404 | 产品未收录，标记"需录入" |
| 17vin API 503 | 标记"API 暂时不可用"，后续补查 |
| Excel 读取失败 | 检查文件格式 (.xls→xlrd, .xlsx→openpyxl)，指定正确 Python 解释器 |
| CDP 不可达 | 检查 Docker 容器状态，提示启动命令 |

### 6.2 Skill 层面

| 错误 | 处理 |
|------|------|
| 泰安联+17vin 均无结果 | 进入电商平台搜索兜底 |
| 泰安联无匹配 | 参数编码问题或 OE 不正确，标记异常 |
| 所有渠道无结果 | 标记"待工厂确认" |

## 7. 未来路线图

- **Redis 缓存**: 缓存 17vin API 结果 (3 分钱/次)，避免重复查询
- **并行批处理**: 非浏览器操作 (parse/backend-search/epc-api) 可并行
- **CloakBrowser 原生部署**: 跳过 Docker，直接用 `python -m cloakbrowser install`
- **自动 CAPTCHA**: 如 CloakBrowser 未来支持，可完全自动化登录
- **Excel 模板**: 标准化输入/输出格式，一键清洗
- **Web Dashboard**: 可视化清洗进度和结果

## 8. 文件清单

| 文件 | 位置 | 类型 |
|------|------|------|
| CloakBrowser SKILL.md | `~/.hermes/skills/browser-automation/cloakbrowser-cli/SKILL.md` | Skill (NEW) |
| CDP Setup Guide | `~/.hermes/skills/browser-automation/cloakbrowser-cli/references/cdp-server-setup.md` | Reference (NEW) |
| Python API Guide | `~/.hermes/skills/browser-automation/cloakbrowser-cli/references/python-api.md` | Reference (NEW) |
| Profile Guide | `~/.hermes/skills/browser-automation/cloakbrowser-cli/references/persistent-profiles.md` | Reference (NEW) |
| data_clean __init__ | `web-project/backend-code-repo/agent-harness/cli_anything/platform_service/core/data_clean/__init__.py` | Code (NEW) |
| factory_parser | `.../data_clean/factory_parser.py` | Code (NEW) |
| backend_api | `.../data_clean/backend_api.py` | Code (NEW) |
| epc | `.../data_clean/epc.py` | Code (NEW) |
| browser_search | `.../data_clean/browser_search.py` | Code (NEW) |
| cross_validate | `.../data_clean/cross_validate.py` | Code (NEW) |
| excel_processor | `.../data_clean/excel_processor.py` | Code (NEW) |
| CLI 主文件 | `.../platform_service_cli.py` | Code (MODIFIED) |
| setup.py | `web-project/backend-code-repo/agent-harness/setup.py` | Code (MODIFIED) |
| Skill 主文件 | `~/.hermes/skills/ruifeng-data-cleaning/SKILL.md` | Skill (MODIFIED) |
| 架构 Spec | `~/.hermes/skills/ruifeng-data-cleaning/references/architecture-spec.md` | Document (NEW) |
