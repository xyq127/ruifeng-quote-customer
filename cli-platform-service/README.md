# cli-anything-platform-service

睿峰智链汽车配件供应链平台 CLI 管理工具。

通过命令行（或 AI Agent）与 platform-service REST API 交互，管理产品、客户/供应商、用户、库存、购物车、采购单、出入库等全部业务模块。

## 安装

### 软件依赖

- 运行中的 platform-service 实例（Spring Boot 后端）
- 有效的 Bearer Token（从 OAuth 服务获取）

### 安装 CLI

```bash
cd agent-harness
pip install -e .
```

## 快速开始

```bash
# 配置连接
cli-anything-platform-service config set --base-url https://api.example.com --token YOUR_TOKEN

# 测试连接
cli-anything-platform-service config test

# 查看产品列表
cli-anything-platform-service product list --page 1 --size 10

# JSON 输出（适合 Agent 消费）
cli-anything-platform-service --json product list --page 1 --size 10

# 进入 REPL 交互模式
cli-anything-platform-service
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `PLATFORM_BASE_URL` | 平台服务 Base URL |
| `PLATFORM_TOKEN` | Bearer Token |

## 命令参考

### 连接配置 (config)
```bash
cli-anything-platform-service config set --base-url URL --token TOKEN
cli-anything-platform-service config show
cli-anything-platform-service config test
cli-anything-platform-service config clear
```

### 产品管理 (product)
```bash
cli-anything-platform-service product list [--keyword KEYWORD] [--page 1] [--size 15]
cli-anything-platform-service product get --id ID
cli-anything-platform-service product create --supplier-id ID --oe OE --code CODE --name NAME ...
cli-anything-platform-service product update --id ID ...
cli-anything-platform-service product delete --id ID
cli-anything-platform-service product on-shelf --id ID
cli-anything-platform-service product off-shelf --id ID
cli-anything-platform-service product sync
cli-anything-platform-service product export [filters...]
```

### 客户/供应商管理 (company)
```bash
cli-anything-platform-service company customer list [filters...]
cli-anything-platform-service company customer get --id ID
cli-anything-platform-service company customer create ...
cli-anything-platform-service company supplier list [filters...]
cli-anything-platform-service company supplier get --id ID
cli-anything-platform-service company audit --id ID --status 1
cli-anything-platform-service company lock --id ID
cli-anything-platform-service company unlock --id ID
```

### 更多命令
使用 `cli-anything-platform-service --help` 或进入 REPL 后输入 `help` 查看全部命令。

## 开发

```bash
pip install -e ".[dev]"
pytest cli_anything/platform_service/tests/ -v
```
