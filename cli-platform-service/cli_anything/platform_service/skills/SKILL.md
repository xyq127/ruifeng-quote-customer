---
name: "睿锋平台CLI"
description: "睿峰智链汽车配件供应链平台 CLI 管理工具。通过命令行与 platform-service REST API 交互，管理产品、客户/供应商、用户、库存、购物车、采购单、出入库等全部业务模块。"
---

# cli-anything-platform-service

睿峰智链汽车配件供应链平台 CLI 管理工具。

## Installation

```bash
cd agent-harness
pip install -e .
```

Requires: Python >= 3.10, click, prompt_toolkit, requests.

## Quick Start

```bash
# Configure connection
cli-anything-platform-service config set --base-url https://api.example.com --token YOUR_TOKEN

# Test connection
cli-anything-platform-service config test

# List products (JSON output for agent consumption)
cli-anything-platform-service --json product list --page 1 --size 10

# Enter interactive REPL mode
cli-anything-platform-service
```

Environment variables: `PLATFORM_BASE_URL`, `PLATFORM_TOKEN`.

## Command Groups

| Command | API Base | Description |
|---------|----------|-------------|
| `config` | - | 连接配置管理 |
| `product` | `/api/product` | 产品管理 (CRUD, 上下架, 导入导出, ES同步) |
| `company` | `/api/company` | 客户/供应商管理 (CRUD, 审核, 锁定/解锁, 认证) |
| `user` | `/api/user` | 用户管理 (CRUD, 企微绑定) |
| `inventory` | `/api/inventory` | 库存管理 (搜索, ES同步) |
| `shopping-cart` | `/api/shoppingCart` | 购物车管理 (CRUD, 批量删除) |
| `price` | `/api/price` | 价格管理 (C0DIG0解析, 报价导出) |
| `quotation` | `/api/quotation` | 报价管理 (CRUD) |
| `purchase-order` | `/api/purchaseOrder` | 采购单管理 (供应商/客户采购单CRUD) |
| `stock-order` | `/api/stockOrder` | 出入库管理 (入库/出库, 库位设置, 过账) |
| `menu` | `/api/menu` | 菜单管理 |
| `role` | `/api/role` | 角色管理 (CRUD) |
| `warehouse` | `/api/warehouse` | 仓库管理 (CRUD) |
| `product-category` | `/api/productCategory` | 产品分类管理 (树形结构, 批量更新) |
| `payment-term` | `/api/paymentTerm` | 付款条件管理 (CRUD) |
| `statement` | `/api/statement` | 对账单管理 (查询, 导出) |

## Agent Usage Guidance

### JSON Output Mode

All commands support `--json` flag for machine-readable output. This is the recommended mode for AI agents.

```bash
cli-anything-platform-service --json product list --page 1 --size 5
```

### Standard Response Format

The API returns a unified `Message` wrapper:
```json
{
  "code": 200,
  "msg": "操作成功",
  "status": true,
  "data": { ... }
}
```

Paginated endpoints return `PageResult`:
```json
{
  "data": {
    "content": [ ... ],
    "totalElements": 100,
    "totalPages": 10,
    "page": 1,
    "size": 15
  }
}
```

### Common Patterns

**CRUD operations** follow RESTful conventions:
```bash
# List
cli-anything-platform-service --json <resource> list [filters...] --page 1 --size 15

# Get by ID
cli-anything-platform-service --json <resource> get --id <UUID>

# Create (POST with required fields)
cli-anything-platform-service --json <resource> create --<field1> <val1> --<field2> <val2> ...

# Update
cli-anything-platform-service --json <resource> update --id <UUID> --<field> <newval> ...

# Delete
cli-anything-platform-service --json <resource> delete --id <UUID>
```

**Field documentation** is available via `comment` sub-command for most resources:
```bash
cli-anything-platform-service --json product comment
```

### Error Handling

- The CLI exits with non-zero status on API errors
- Error messages are in Chinese
- HTTP 401 = token expired/invalid
- HTTP 403 = insufficient permissions
- HTTP 404 = resource not found

### Configuration Persistence

Config is saved to `~/.cli-anything-platform-service/config.json`. Tokens are stored and can be pre-configured via `config set`.
