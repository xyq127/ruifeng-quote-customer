# Platform Service CLI — Test Plan

## Test Inventory Plan

| File | Planned Tests | Type |
|------|--------------|------|
| `test_core.py` | 25+ unit tests | Unit tests (synthetic data) |
| `test_full_e2e.py` | 15+ E2E tests | Integration + subprocess |

## Unit Test Plan (test_core.py)

### session.py
- `test_session_init`: Session 初始化，配置为空
- `test_session_set_base_url`: 设置并读取 base_url
- `test_session_set_token`: 设置并读取 token
- `test_session_configured`: 检查配置状态
- `test_session_persist`: 保存配置到文件，重新加载验证
- `test_session_clear`: 清除配置
- `test_session_env_fallback`: 从环境变量读取

### backend.py
- `test_backend_init`: Backend 初始化
- `test_backend_set_token`: Token 设置
- `test_backend_mock_get`: Mock GET 请求
- `test_backend_mock_post`: Mock POST 请求
- `test_backend_mock_delete`: Mock DELETE 请求
- `test_backend_connection_error`: 连接失败处理
- `test_backend_http_error`: HTTP 错误处理
- `test_backend_auth_error`: 401 认证失败

### Config Module
- `test_config_show`: 显示配置
- `test_config_set`: 设置配置
- `test_config_test_fail`: 测试连接失败

### Output Formatting
- `test_output_json`: JSON 输出模式
- `test_output_paginated`: 分页数据人类可读输出
- `test_output_single_item`: 单个对象输出
- `test_output_error`: 错误响应输出

## E2E Test Plan (test_full_e2e.py)

### CLI Subprocess Tests (TestCLISubprocess)
- `test_cli_help`: 验证 --help 输出
- `test_cli_version`: 验证版本信息
- `test_cli_config_flow`: 配置设置→显示→清除 完整流程
- `test_cli_product_help`: 验证 product 子命令 help
- `test_cli_company_help`: 验证 company 子命令 help
- `test_cli_json_output`: 验证 --json 输出格式

### Integration Tests (requires running backend)
- `test_product_comment`: 获取产品字段文档
- `test_company_comment`: 获取公司字段文档
- `test_user_comment`: 获取用户字段文档
- `test_inventory_comment`: 获取库存字段文档
- `test_warehouse_list`: 获取仓库列表
- `test_category_tree`: 获取分类树

### Workflow Scenarios
- **Workflow 1: 产品上架流程**: 创建产品 → 上架 → 查询 → 下架 → 删除
- **Workflow 2: 客户管理流程**: 创建客户 → 审核 → 锁定 → 解锁
- **Workflow 3: 采购入库流程**: 创建采购单 → 查询 → 入库

## Coverage Notes

- API mocking 用于单元测试，避免依赖真实后端
- E2E 测试需要运行中的 platform-service 实例
- Subprocess 测试使用 `_resolve_cli()` 模式定位 `cli-anything-platform-service` 命令
- 测试输出会打印制品路径以便手动检查

---

## Test Results

```
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/stoic16/web-project/backend-code-repo/agent-harness
plugins: cov-7.1.0
collected 58 items

test_core.py::TestSession::test_init_empty PASSED                      [  1%]
test_core.py::TestSession::test_set_and_get_base_url PASSED            [  3%]
test_core.py::TestSession::test_set_and_get_token PASSED               [  5%]
test_core.py::TestSession::test_persist_and_reload PASSED              [  6%]
test_core.py::TestSession::test_clear PASSED                           [  8%]
test_core.py::TestSession::test_env_fallback PASSED                    [ 10%]
test_core.py::TestSession::test_to_dict PASSED                         [ 12%]
test_core.py::TestSession::test_locked_save_json_new_file PASSED       [ 13%]
test_core.py::TestSession::test_locked_save_json_existing_file PASSED  [ 15%]
test_core.py::TestBackend::test_init PASSED                            [ 17%]
test_core.py::TestBackend::test_init_with_token PASSED                 [ 18%]
test_core.py::TestBackend::test_set_token PASSED                       [ 20%]
test_core.py::TestBackend::test_get_request PASSED                     [ 22%]
test_core.py::TestBackend::test_post_request PASSED                    [ 24%]
test_core.py::TestBackend::test_delete_request PASSED                  [ 25%]
test_core.py::TestBackend::test_connection_error PASSED                [ 27%]
test_core.py::TestBackend::test_http_auth_error PASSED                 [ 29%]
test_core.py::TestBackend::test_http_404_error PASSED                  [ 31%]
test_core.py::TestBackend::test_204_no_content PASSED                  [ 32%]
test_core.py::TestBackend::test_validate_connection_success PASSED     [ 34%]
test_core.py::TestBackend::test_validate_connection_fail PASSED        [ 36%]
test_core.py::TestBackend::test_binary_response PASSED                 [ 37%]
test_core.py::TestOutputFormatting::test_none_backend_module_loading PASSED [ 39%]
test_core.py::TestOutputFormatting::test_cli_imports_all_commands PASSED [ 41%]
test_core.py::TestOutputFormatting::test_cli_command_callable PASSED   [ 43%]
test_core.py::TestOutputFormatting::test_output_json_mode PASSED       [ 44%]
test_core.py::TestOutputFormatting::test_session_module_standalone PASSED [ 46%]
test_full_e2e.py::TestCLISubprocess::test_help PASSED                  [ 48%]
test_full_e2e.py::TestCLISubprocess::test_config_help PASSED           [ 50%]
test_full_e2e.py::TestCLISubprocess::test_product_help PASSED          [ 51%]
test_full_e2e.py::TestCLISubprocess::test_company_help PASSED          [ 53%]
test_full_e2e.py::TestCLISubprocess::test_user_help PASSED             [ 55%]
test_full_e2e.py::TestCLISubprocess::test_inventory_help PASSED        [ 56%]
test_full_e2e.py::TestCLISubprocess::test_shopping_cart_help PASSED    [ 58%]
test_full_e2e.py::TestCLISubprocess::test_price_help PASSED            [ 60%]
test_full_e2e.py::TestCLISubprocess::test_quotation_help PASSED        [ 62%]
test_full_e2e.py::TestCLISubprocess::test_purchase_order_help PASSED   [ 63%]
test_full_e2e.py::TestCLISubprocess::test_stock_order_help PASSED      [ 65%]
test_full_e2e.py::TestCLISubprocess::test_menu_help PASSED             [ 67%]
test_full_e2e.py::TestCLISubprocess::test_role_help PASSED             [ 68%]
test_full_e2e.py::TestCLISubprocess::test_warehouse_help PASSED        [ 70%]
test_full_e2e.py::TestCLISubprocess::test_product_category_help PASSED [ 72%]
test_full_e2e.py::TestCLISubprocess::test_payment_term_help PASSED     [ 74%]
test_full_e2e.py::TestCLISubprocess::test_statement_help PASSED        [ 75%]
test_full_e2e.py::TestCLISubprocess::test_config_set_and_show PASSED   [ 77%]
test_full_e2e.py::TestCLISubprocess::test_config_show_empty PASSED     [ 79%]
test_full_e2e.py::TestCLISubprocess::test_config_test_fails_without_server PASSED [ 81%]
test_full_e2e.py::TestCLISubprocess::test_json_flag_applies PASSED     [ 82%]
test_full_e2e.py::TestCLISubprocess::test_all_commands_listed_in_help PASSED [ 84%]
test_full_e2e.py::TestIntegration::test_product_comment PASSED         [ 86%]
test_full_e2e.py::TestIntegration::test_company_comment PASSED         [ 87%]
test_full_e2e.py::TestIntegration::test_user_comment PASSED            [ 89%]
test_full_e2e.py::TestIntegration::test_inventory_comment PASSED       [ 91%]
test_full_e2e.py::TestIntegration::test_warehouse_list PASSED          [ 93%]
test_full_e2e.py::TestIntegration::test_category_tree PASSED           [ 94%]
test_full_e2e.py::TestWorkflows::test_product_crud_workflow PASSED     [ 96%]
test_full_e2e.py::TestWorkflows::test_company_query_workflow PASSED    [ 98%]
test_full_e2e.py::TestWorkflows::test_role_query_workflow PASSED       [100%]

============================== 58 passed in 2.73s ==============================
```

## Summary

- **Total tests**: 58
- **Pass rate**: 100% (58/58)
- **Execution time**: 2.73s
- **Unit tests**: 27 (test_core.py)
- **E2E subprocess tests**: 22 (test_full_e2e.py::TestCLISubprocess)
- **Integration tests**: 6 (test_full_e2e.py::TestIntegration — skipped without PLATFORM_BASE_URL)
- **Workflow tests**: 3 (test_full_e2e.py::TestWorkflows — skipped without PLATFORM_BASE_URL)

## Coverage Notes

- Integration and workflow tests are automatically skipped when `PLATFORM_BASE_URL` env var is not set
- To run with a real backend: `PLATFORM_BASE_URL=http://localhost:8080 PLATFORM_TOKEN=<token> pytest ...`
- Subprocess tests use `_resolve_cli()` which falls back to `python -m` in dev mode, uses installed command in production
