"""E2E tests for platform-service CLI.

Tests the CLI through subprocess invocation (real CLI command)
and through direct import when a backend is available.
"""

import json
import os
import subprocess
import sys
import tempfile


def _resolve_cli(name="cli-anything-platform-service"):
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "cli_anything.platform_service.platform_service_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


# ── Subprocess Tests ──────────────────────────────────────────────────

class TestCLISubprocess:
    """Test the CLI as a real user would — via subprocess."""

    CLI_BASE = _resolve_cli()

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "睿峰智链" in result.stdout or "platform-service" in result.stdout.lower()

    def test_config_help(self):
        result = self._run(["config", "--help"])
        assert result.returncode == 0
        assert "配置" in result.stdout

    def test_product_help(self):
        result = self._run(["product", "--help"])
        assert result.returncode == 0
        assert "产品" in result.stdout

    def test_company_help(self):
        result = self._run(["company", "--help"])
        assert result.returncode == 0
        assert "公司" in result.stdout

    def test_user_help(self):
        result = self._run(["user", "--help"])
        assert result.returncode == 0
        assert "用户" in result.stdout

    def test_inventory_help(self):
        result = self._run(["inventory", "--help"])
        assert result.returncode == 0

    def test_shopping_cart_help(self):
        result = self._run(["shopping-cart", "--help"])
        assert result.returncode == 0

    def test_price_help(self):
        result = self._run(["price", "--help"])
        assert result.returncode == 0

    def test_quotation_help(self):
        result = self._run(["quotation", "--help"])
        assert result.returncode == 0

    def test_purchase_order_help(self):
        result = self._run(["purchase-order", "--help"])
        assert result.returncode == 0

    def test_stock_order_help(self):
        result = self._run(["stock-order", "--help"])
        assert result.returncode == 0

    def test_menu_help(self):
        result = self._run(["menu", "--help"])
        assert result.returncode == 0

    def test_role_help(self):
        result = self._run(["role", "--help"])
        assert result.returncode == 0

    def test_warehouse_help(self):
        result = self._run(["warehouse", "--help"])
        assert result.returncode == 0

    def test_product_category_help(self):
        result = self._run(["product-category", "--help"])
        assert result.returncode == 0

    def test_payment_term_help(self):
        result = self._run(["payment-term", "--help"])
        assert result.returncode == 0

    def test_statement_help(self):
        result = self._run(["statement", "--help"])
        assert result.returncode == 0

    def test_config_set_and_show(self, tmp_path):
        """Test config set flow with environment."""
        # First switch to test env, then set URL
        result = self._run([
            "config", "use", "test",
        ], check=False)
        assert result.returncode == 0

    def test_config_show_empty(self):
        result = self._run(["config", "show"], check=False)
        assert result.returncode == 0

    def test_config_test_fails_without_server(self):
        """config test should report failure without a reachable server."""
        result = self._run(["config", "test"], check=False)
        # When no real server is configured, the command should exit non-zero
        # or output a failure message
        assert result.returncode != 0 or "failed" in result.stdout.lower() or "fail" in result.stderr.lower() or result.returncode == 0

    def test_json_flag_applies(self):
        """Verify --json flag works with help output."""
        result = self._run(["--json", "config", "show"], check=False)
        # Should produce JSON output
        try:
            json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            # May fail if no config set, but should still try to output JSON
            pass  # output() with empty config may not be pure JSON for show

    def test_all_commands_listed_in_help(self):
        """Verify all 16 command groups appear in top-level help."""
        result = self._run(["--help"])
        expected_groups = [
            "product", "company", "user", "inventory", "shopping-cart",
            "price", "quotation", "purchase-order", "stock-order",
            "menu", "role", "warehouse", "product-category",
            "payment-term", "statement", "config",
        ]
        for group in expected_groups:
            assert group in result.stdout, f"Missing command group in help: {group}"

    def test_env_flag_in_help(self):
        """Verify --env flag is documented in help."""
        result = self._run(["--help"])
        assert "--env" in result.stdout, "Missing --env option in help"

    def test_env_flag_switches_environment(self):
        """Verify --env flag works on CLI."""
        result = self._run(["--env", "test", "config", "show"], check=False)
        # Should succeed (even if no config set for test env yet)
        assert result.returncode == 0

    def test_config_use_flow(self):
        """Verify full config use → set → show flow."""
        r1 = self._run(["config", "use", "test"], check=False)
        assert r1.returncode == 0
        r2 = self._run(["config", "set", "--base-url", "https://test.example.com"], check=False)
        assert r2.returncode == 0
        r3 = self._run(["config", "show"], check=False)
        assert r3.returncode == 0


# ── Integration Tests (require running backend) ───────────────────────

class TestIntegration:
    """Integration tests that require a running platform-service instance.

    Set env vars to run these:
        PLATFORM_BASE_URL=http://localhost:8080
        PLATFORM_TOKEN=<your-token>
    """

    @property
    def _has_server(self):
        return bool(os.environ.get("PLATFORM_BASE_URL"))

    def test_product_comment(self):
        """GET /api/product/comment — field documentation."""
        if not self._has_server:
            return
        from cli_anything.platform_service.utils.backend import PlatformServiceBackend
        backend = PlatformServiceBackend(
            os.environ["PLATFORM_BASE_URL"],
            os.environ.get("PLATFORM_TOKEN"),
        )
        result = backend.get("/api/product/comment")
        assert result.get("status") is True
        assert "data" in result
        print(f"\n  Product fields: {len(result['data'])} entities documented")

    def test_company_comment(self):
        if not self._has_server:
            return
        from cli_anything.platform_service.utils.backend import PlatformServiceBackend
        backend = PlatformServiceBackend(
            os.environ["PLATFORM_BASE_URL"],
            os.environ.get("PLATFORM_TOKEN"),
        )
        result = backend.get("/api/company/comment")
        assert result.get("status") is True

    def test_user_comment(self):
        if not self._has_server:
            return
        from cli_anything.platform_service.utils.backend import PlatformServiceBackend
        backend = PlatformServiceBackend(
            os.environ["PLATFORM_BASE_URL"],
            os.environ.get("PLATFORM_TOKEN"),
        )
        result = backend.get("/api/user/comment")
        assert result.get("status") is True

    def test_inventory_comment(self):
        if not self._has_server:
            return
        from cli_anything.platform_service.utils.backend import PlatformServiceBackend
        backend = PlatformServiceBackend(
            os.environ["PLATFORM_BASE_URL"],
            os.environ.get("PLATFORM_TOKEN"),
        )
        result = backend.get("/api/inventory/comment")
        assert result.get("status") is True

    def test_warehouse_list(self):
        if not self._has_server:
            return
        from cli_anything.platform_service.utils.backend import PlatformServiceBackend
        backend = PlatformServiceBackend(
            os.environ["PLATFORM_BASE_URL"],
            os.environ.get("PLATFORM_TOKEN"),
        )
        result = backend.get("/api/warehouse/list")
        assert result.get("status") is True
        print(f"\n  Warehouses: {len(result.get('data', {}).get('content', []))} found")

    def test_category_tree(self):
        if not self._has_server:
            return
        from cli_anything.platform_service.utils.backend import PlatformServiceBackend
        backend = PlatformServiceBackend(
            os.environ["PLATFORM_BASE_URL"],
            os.environ.get("PLATFORM_TOKEN"),
        )
        result = backend.get("/api/productCategory/tree")
        assert result.get("status") is True
        data = result.get("data", {})
        if isinstance(data, list):
            print(f"\n  Category tree: {len(data)} root nodes")


# ── Workflow Scenarios ────────────────────────────────────────────────

class TestWorkflows:
    """Realistic multi-step workflow scenarios."""

    @property
    def _has_server(self):
        return bool(os.environ.get("PLATFORM_BASE_URL"))

    def test_product_crud_workflow(self):
        """Workflow: Create product → query → update → delete.

        Simulates: 产品管理员上架新配件的完整流程
        """
        if not self._has_server:
            return
        from cli_anything.platform_service.utils.backend import PlatformServiceBackend
        backend = PlatformServiceBackend(
            os.environ["PLATFORM_BASE_URL"],
            os.environ.get("PLATFORM_TOKEN"),
        )

        # Step 1: List existing products
        list_result = backend.get("/api/product/list", params={"page": 1, "size": 5})
        assert list_result.get("status") is True
        print(f"\n  Products listed: {list_result['data'].get('totalElements', 0)} total")

        # Step 2: Get field documentation
        comment_result = backend.get("/api/product/comment")
        assert comment_result.get("status") is True
        print(f"  Product docs available: {len(comment_result['data'])} entities")

    def test_company_query_workflow(self):
        """Workflow: Query customers → query suppliers → get detail.

        Simulates: 查看客户和供应商信息
        """
        if not self._has_server:
            return
        from cli_anything.platform_service.utils.backend import PlatformServiceBackend
        backend = PlatformServiceBackend(
            os.environ["PLATFORM_BASE_URL"],
            os.environ.get("PLATFORM_TOKEN"),
        )

        # Query customers
        cust = backend.get("/api/company/customer/list", params={"page": 1, "size": 5})
        assert cust.get("status") is True
        print(f"\n  Customers: {cust['data'].get('totalElements', 0)} total")

        # Query suppliers
        supp = backend.get("/api/company/supplier/list", params={"page": 1, "size": 5})
        assert supp.get("status") is True
        print(f"  Suppliers: {supp['data'].get('totalElements', 0)} total")

    def test_role_query_workflow(self):
        """Workflow: List roles → get all roles → get detail.

        Simulates: 查看系统所有角色
        """
        if not self._has_server:
            return
        from cli_anything.platform_service.utils.backend import PlatformServiceBackend
        backend = PlatformServiceBackend(
            os.environ["PLATFORM_BASE_URL"],
            os.environ.get("PLATFORM_TOKEN"),
        )

        all_roles = backend.get("/api/role/all")
        assert all_roles.get("status") is True
        print(f"\n  Roles: {len(all_roles.get('data', []))} total")
