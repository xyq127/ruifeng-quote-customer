# Platform Service CLI — SOP & Architecture

## 软件概述

睿峰智链汽车配件供应链平台后端服务。Java Spring Boot 多模块 Maven 工程，为管理后台和客户前端提供 REST API。

### 模块结构

| 模块 | 说明 |
|------|------|
| `principal-service` | 核心业务服务（产品、公司、用户、库存、购物车、采购单、出入库等 15 个业务域） |
| `oauth-service` | OAuth2 认证服务 |
| `gateway-service` | API 网关 |
| `common-service` | 公共类库（Base Entity、Message 响应体、工具类） |
| `analysis-service` | 数据分析服务 |

### 技术栈

- **语言**: Java 8
- **框架**: Spring Boot 2.2.1
- **安全**: Spring Security OAuth2 (JWT)
- **数据库**: MySQL + JPA
- **搜索引擎**: Elasticsearch
- **构建**: Maven

## CLI 架构

### 交互模型

- **终端用户**: `cli-anything-platform-service` 命令 + 子命令
- **Agent 调用**: `--json` 模式 + 子命令
- **REPL 模式**: 默认行为，支持交互式探索

### 命令分组

| 命令组 | 对应业务域 | API 前缀 |
|--------|-----------|---------|
| `config` | 连接配置 | - |
| `product` | 产品管理 | `/api/product` |
| `company` | 客户/供应商管理 | `/api/company` |
| `user` | 用户管理 | `/api/user` |
| `inventory` | 库存管理 | `/api/inventory` |
| `shopping-cart` | 购物车 | `/api/shoppingCart` |
| `price` | 价格管理 | `/api/price` |
| `quotation` | 报价管理 | `/api/quotation` |
| `purchase-order` | 采购单管理 | `/api/purchaseOrder` |
| `stock-order` | 出入库管理 | `/api/stockOrder` |
| `menu` | 菜单管理 | `/api/menu` |
| `role` | 角色管理 | `/api/role` |
| `warehouse` | 仓库管理 | `/api/warehouse` |
| `product-category` | 产品分类 | `/api/productCategory` |
| `payment-term` | 付款条件 | `/api/paymentTerm` |
| `statement` | 对账单 | `/api/statement` |

### 状态模型

- **会话配置**: JSON 文件 `~/.cli-anything-platform-service/config.json`，含 `base_url` 和 `token`
- **环境变量**: `PLATFORM_BASE_URL`, `PLATFORM_TOKEN`
- **运行时**: Python 全局变量，仅在进程内有效

### 后端交互

CLI → HTTP (Bearer Token) → Spring Boot REST API → JSON (Message 格式)

标准响应:
```json
{"code": 200, "msg": "操作成功", "status": true, "data": {...}}
```

### 数据流

```
CLI 命令 → 参数解析 → HTTP Request → API Response → 格式化输出 (人类/JSON)
```

## "Real Software" 依赖

本 CLI 的 "真实软件" 是运行中的 platform-service Spring Boot 应用。调用者必须:

1. 确认目标服务已启动
2. 提供正确的 Base URL
3. 持有有效的 Bearer Token

```
# 开发环境示例
cli-anything-platform-service config set --base-url http://localhost:8080 --token <token>
```
