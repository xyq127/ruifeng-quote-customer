"""Unit tests for platform-service CLI core modules.

Uses synthetic data and mocking — no external dependencies required.
"""

import json
import os
import tempfile
from unittest import mock

from click.testing import CliRunner

from cli_anything.platform_service.core.session import Session, _locked_save_json, _load_json
from cli_anything.platform_service.utils.backend import PlatformServiceBackend
# 先导入 platform_service_cli 完成模块初始化，避免 data_clean.backend_api 的循环导入
import cli_anything.platform_service.platform_service_cli  # noqa: F401
from cli_anything.platform_service.core.data_clean.backend_api import _search_with_retry_chain
from cli_anything.platform_service.core.data_clean.factory_parser import classify_match
from cli_anything.platform_service.core.data_clean import cache as cache_module
from cli_anything.platform_service.core.data_clean.cache import _cache_key, get_cached, set_cached


# ── Session tests ─────────────────────────────────────────────────────

class TestSession:
    def test_init_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cfg_path = f.name
        try:
            s = Session(config_path=cfg_path)
            assert s.current_env is None
            assert s.base_url is None
            assert s.token is None
            assert not s.configured
        finally:
            os.unlink(cfg_path)

    def test_set_and_get_base_url(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cfg_path = f.name
        try:
            s = Session(config_path=cfg_path)
            s.current_env = "test"
            s.base_url = "https://api.example.com"
            assert s.base_url == "https://api.example.com"
            assert s.configured
        finally:
            os.unlink(cfg_path)

    def test_set_and_get_token(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cfg_path = f.name
        try:
            s = Session(config_path=cfg_path)
            s.current_env = "test"
            s.token = "my-secret-token"
            assert s.token == "my-secret-token"
        finally:
            os.unlink(cfg_path)

    def test_persist_and_reload(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cfg_path = f.name
        try:
            s1 = Session(config_path=cfg_path)
            s1.current_env = "test"
            s1.base_url = "https://persist.example.com"
            s1.token = "persist-token"

            s2 = Session(config_path=cfg_path)
            assert s2.current_env == "test"
            assert s2.base_url == "https://persist.example.com"
            assert s2.token == "persist-token"
            assert s2.configured
        finally:
            os.unlink(cfg_path)

    def test_switch_environment(self):
        """Test switching between environments preserves per-env config."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cfg_path = f.name
        try:
            s = Session(config_path=cfg_path)
            # Configure test env
            s.current_env = "test"
            s.base_url = "https://test.example.com"
            s.token = "test-token"
            # Configure prod env
            s.current_env = "prod"
            s.base_url = "https://prod.example.com"
            s.token = "prod-token"
            # Switch back to test and verify
            s.current_env = "test"
            assert s.base_url == "https://test.example.com"
            assert s.token == "test-token"
            # Verify prod is still there
            envs = s.list_envs()
            assert envs["test"]["base_url"] == "https://test.example.com"
            assert envs["prod"]["base_url"] == "https://prod.example.com"
        finally:
            os.unlink(cfg_path)

    def test_clear_env(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cfg_path = f.name
        try:
            s = Session(config_path=cfg_path)
            s.current_env = "test"
            s.base_url = "https://test.example.com"
            s.clear(env="test")
            assert s.current_env is None
            assert s.base_url is None
        finally:
            os.unlink(cfg_path)

    def test_clear_all(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cfg_path = f.name
        try:
            s = Session(config_path=cfg_path)
            s.current_env = "test"
            s.base_url = "https://test.example.com"
            s.clear()
            assert s.base_url is None
            assert not os.path.exists(cfg_path)
        finally:
            if os.path.exists(cfg_path):
                os.unlink(cfg_path)

    def test_env_fallback(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cfg_path = f.name
        try:
            os.environ["PLATFORM_BASE_URL"] = "https://env.example.com"
            os.environ["PLATFORM_TOKEN"] = "env-token"
            s = Session(config_path=cfg_path)
            # Env vars still work as fallback when no per-env config
            assert s.base_url == "https://env.example.com"
            assert s.token == "env-token"
        finally:
            os.unlink(cfg_path)
            del os.environ["PLATFORM_BASE_URL"]
            del os.environ["PLATFORM_TOKEN"]

    def test_to_dict(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cfg_path = f.name
        try:
            s = Session(config_path=cfg_path)
            s.current_env = "test"
            s.base_url = "https://dict.example.com"
            s.token = "secret123"
            d = s.to_dict()
            assert d["current_env"] == "test"
            assert d["base_url"] == "https://dict.example.com"
            assert d["token"] == "***"
            assert "config_path" in d
            assert "environments" in d
        finally:
            os.unlink(cfg_path)

    def test_list_envs(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cfg_path = f.name
        try:
            s = Session(config_path=cfg_path)
            envs = s.list_envs()
            assert "test" in envs
            assert "prod" in envs
            assert envs["test"]["server"] == "8.155.167.214"
            assert envs["prod"]["server"] == "8.155.164.3"
        finally:
            os.unlink(cfg_path)

    def test_invalid_env_rejected(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cfg_path = f.name
        try:
            s = Session(config_path=cfg_path)
            try:
                s.current_env = "staging"
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "未知环境" in str(e)
        finally:
            os.unlink(cfg_path)

    def test_base_url_without_env_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cfg_path = f.name
        try:
            s = Session(config_path=cfg_path)
            try:
                s.base_url = "https://no-env.example.com"
                assert False, "Should have raised RuntimeError"
            except RuntimeError as e:
                assert "请先设置当前环境" in str(e)
        finally:
            os.unlink(cfg_path)

    def test_locked_save_json_new_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        os.unlink(path)
        try:
            _locked_save_json(path, {"key": "value"}, indent=2)
            assert os.path.exists(path)
            loaded = _load_json(path)
            assert loaded == {"key": "value"}
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_locked_save_json_existing_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"old": "data"}, f)
            path = f.name
        try:
            _locked_save_json(path, {"new": "data"})
            loaded = _load_json(path)
            assert loaded == {"new": "data"}
        finally:
            os.unlink(path)


# ── Backend tests ─────────────────────────────────────────────────────

class TestBackend:
    def test_init(self):
        b = PlatformServiceBackend("https://api.example.com")
        assert b.base_url == "https://api.example.com"
        assert b.token is None
        assert "Authorization" not in b.headers

    def test_init_with_token(self):
        b = PlatformServiceBackend("https://api.example.com", token="abc123")
        assert b.token == "abc123"
        assert b.headers["Authorization"] == "Bearer abc123"

    def test_set_token(self):
        b = PlatformServiceBackend("https://api.example.com")
        b.set_token("new-token")
        assert b.token == "new-token"
        assert b.headers["Authorization"] == "Bearer new-token"

    @mock.patch("cli_anything.platform_service.utils.backend.requests.Session.get")
    def test_get_request(self, mock_get):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.json.return_value = {"code": 200, "msg": "OK", "status": True, "data": {"items": []}}
        mock_get.return_value = mock_resp

        b = PlatformServiceBackend("https://api.example.com")
        result = b.get("/api/test/list", params={"page": 1})
        assert result["code"] == 200
        mock_get.assert_called_once()

    @mock.patch("cli_anything.platform_service.utils.backend.requests.Session.post")
    def test_post_request(self, mock_post):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.json.return_value = {"code": 200, "msg": "保存成功", "status": True, "data": None}
        mock_post.return_value = mock_resp

        b = PlatformServiceBackend("https://api.example.com")
        result = b.post("/api/product/save", data={"name": "test"})
        assert result["status"] is True
        mock_post.assert_called_once()

    @mock.patch("cli_anything.platform_service.utils.backend.requests.Session.post")
    def test_post_request_with_files_omits_json_content_type(self, mock_post):
        """multipart 上传 (files=) 不应固定 Content-Type: application/json,

        否则后端会返回 415 Unsupported Media Type (实测 /productAudit/parse)。
        应交由 requests 根据 files 自动生成带 boundary 的
        multipart/form-data Content-Type。
        """
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.json.return_value = {"code": 200, "msg": "OK", "status": True, "data": None}
        mock_post.return_value = mock_resp

        b = PlatformServiceBackend("https://api.example.com", token="abc123")
        result = b.post("/api/productAudit/parse", data={"queryRange": "0,1,2,3,4"},
                         files={"file": ("a.xlsx", b"fake-bytes", "application/octet-stream")})
        assert result["status"] is True

        _, kwargs = mock_post.call_args
        sent_headers = kwargs.get("headers", {})
        assert "Content-Type" not in sent_headers
        # 其余 header (如 Authorization) 仍应保留
        assert sent_headers.get("Authorization") == "Bearer abc123"
        assert kwargs.get("files") is not None

    @mock.patch("cli_anything.platform_service.utils.backend.requests.Session.delete")
    def test_delete_request(self, mock_delete):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.json.return_value = {"code": 200, "msg": "删除成功", "status": True, "data": None}
        mock_delete.return_value = mock_resp

        b = PlatformServiceBackend("https://api.example.com")
        result = b.delete("/api/product/delete", params={"id": "123"})
        assert result["status"] is True
        mock_delete.assert_called_once()

    @mock.patch("cli_anything.platform_service.utils.backend.requests.Session.get")
    def test_connection_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        b = PlatformServiceBackend("https://api.example.com")
        try:
            b.get("/api/test")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "无法连接到平台服务" in str(e)

    @mock.patch("cli_anything.platform_service.utils.backend.requests.Session.get")
    def test_http_auth_error(self, mock_get):
        import requests
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        http_err = requests.exceptions.HTTPError(response=mock_resp)
        mock_get.side_effect = http_err

        b = PlatformServiceBackend("https://api.example.com")
        try:
            b.get("/api/test")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "Token 无效" in str(e) or "认证失败" in str(e)

    @mock.patch("cli_anything.platform_service.utils.backend.requests.Session.get")
    def test_http_404_error(self, mock_get):
        import requests
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "Not Found"
        http_err = requests.exceptions.HTTPError(response=mock_resp)
        mock_get.side_effect = http_err

        b = PlatformServiceBackend("https://api.example.com")
        try:
            b.get("/api/nonexistent")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "资源不存在" in str(e)

    @mock.patch("cli_anything.platform_service.utils.backend.requests.Session.get")
    def test_204_no_content(self, mock_get):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 204
        mock_get.return_value = mock_resp

        b = PlatformServiceBackend("https://api.example.com")
        result = b.get("/api/test")
        assert result["code"] == 204

    @mock.patch("cli_anything.platform_service.utils.backend.requests.Session.get")
    def test_validate_connection_success(self, mock_get):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.json.return_value = {"code": 200, "status": True, "data": {}}
        mock_get.return_value = mock_resp

        b = PlatformServiceBackend("https://api.example.com")
        assert b.validate_connection() is True

    @mock.patch("cli_anything.platform_service.utils.backend.requests.Session.get")
    def test_validate_connection_fail(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()

        b = PlatformServiceBackend("https://api.example.com")
        assert b.validate_connection() is False

    @mock.patch("cli_anything.platform_service.utils.backend.requests.Session.get")
    def test_binary_response(self, mock_get):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        mock_resp.content = b"fake-excel-data"
        mock_get.return_value = mock_resp

        b = PlatformServiceBackend("https://api.example.com")
        result = b.get("/api/product/export")
        assert result["code"] == 200
        assert "content_type" in result["data"]
        assert "spreadsheetml" in result["data"]["content_type"]
    def test_internal_platform_hosts_ignore_proxy_env(self):
        b = PlatformServiceBackend("https://rfscm.com/api/principal")
        assert b.session.trust_env is False

        b = PlatformServiceBackend("https://external.example.com")
        assert b.session.trust_env is True


# ── Product CLI contract tests ────────────────────────────────────────

class TestProductCli:
    def test_product_create_maps_backend_contract_fields(self):
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.platform_service_cli as cli_module

        calls = []

        class FakeBackend:
            def post(self, path, data=None, params=None, files=None):
                calls.append((path, data, params, files))
                return {"code": 200, "msg": "OK", "status": True, "data": None}

        runner = CliRunner()
        with mock.patch.object(cli_module, "Session") as mock_session, \
             mock.patch.object(cli_module, "PlatformServiceBackend", return_value=FakeBackend()):
            session = mock.MagicMock()
            session.base_url = "https://api.example.com/api/principal"
            session.token = "token"
            session.current_env = "test"
            mock_session.return_value = session

            result = runner.invoke(cli, [
                "--json", "product", "create",
                "--supplier-id", "S001",
                "--oe", "OE001",
                "--code", "C001",
                "--name", "NewProduct",
                "--brand", "Brand",
                "--car", "全车系",
                "--company-car-id", "CAR001",
                "--car-code", "CARCODE",
                "--category-id", "CAT001",
                "--sale-unit", "1",
                "--presale", "true",
                "--self-support", "false",
                "--new-product", "是",
                "--weight", "01.20",
                "--volume", "10*20*30",
                "--rate-num", "001234",
                "--params-json", '[{"paramId":"p1","paramValue":"v1"}]',
                "--ext-data-json", '{"newEnergyAdapt":1}',
                "--attachment-price", "3.5",
                "--suggest-type", "1",
            ])

        assert result.exit_code == 0, result.output
        assert len(calls) == 1
        path, data, params, files = calls[0]
        assert path == "/api/product/save"
        assert params is None
        assert files is None
        assert data["supplierId"] == "S001"
        assert data["companyCarId"] == "CAR001"
        assert data["saleUnit"] == 1
        assert data["presale"] is True
        assert data["selfSupport"] is False
        assert data["newProduct"] is True
        assert data["weight"] == "01.20"
        assert data["volume"] == "10*20*30"
        assert data["rateNum"] == "001234"
        assert data["params"] == [{"paramId": "p1", "paramValue": "v1"}]
        assert "paramsJson" not in data
        assert data["extDataJson"] == '{"newEnergyAdapt":1}'
        assert data["attachmentPrice"] == 3.5
        assert data["suggestType"] == 1

    def test_product_create_requires_params_json(self):
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.platform_service_cli as cli_module

        class FakeBackend:
            def post(self, path, data=None, params=None, files=None):
                return {"code": 200, "msg": "OK", "status": True, "data": None}

        runner = CliRunner()
        with mock.patch.object(cli_module, "Session") as mock_session, \
             mock.patch.object(cli_module, "PlatformServiceBackend", return_value=FakeBackend()):
            session = mock.MagicMock()
            session.base_url = "https://api.example.com/api/principal"
            session.token = "token"
            session.current_env = "test"
            mock_session.return_value = session

            result = runner.invoke(cli, [
                "--json", "product", "create",
                "--supplier-id", "S001",
                "--oe", "OE001",
                "--code", "C001",
                "--name", "NewProduct",
                "--brand", "Brand",
                "--car", "全车系",
                "--company-car-id", "CAR001",
                "--car-code", "CARCODE",
                "--category-id", "CAT001",
            ])

        assert result.exit_code != 0
        assert "Missing option '--params-json'" in result.output

    def test_product_update_maps_backend_contract_fields(self):
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.platform_service_cli as cli_module

        calls = []

        class FakeBackend:
            def post(self, path, data=None, params=None, files=None):
                calls.append((path, data, params, files))
                return {"code": 200, "msg": "OK", "status": True, "data": None}

        runner = CliRunner()
        with mock.patch.object(cli_module, "Session") as mock_session, \
             mock.patch.object(cli_module, "PlatformServiceBackend", return_value=FakeBackend()):
            session = mock.MagicMock()
            session.base_url = "https://api.example.com/api/principal"
            session.token = "token"
            session.current_env = "test"
            mock_session.return_value = session

            result = runner.invoke(cli, [
                "--json", "product", "update",
                "--id", "P001",
                "--name", "NewName",
                "--company-car-id", "CAR001",
                "--oem-price", "12.5",
                "--presale", "true",
                "--self-support", "false",
                "--new-product", "1",
                "--weight", "01.20",
                "--volume", "10*20*30",
                "--rate-num", "001234",
                "--params-json", '[{"paramId":"p1","paramValue":"v1"}]',
                "--ext-data-json", '{"newEnergyAdapt":1}',
                "--main-vehicle-model", "主车型",
                "--reference-vehicle-model", "通用车型",
                "--suggest-type", "1",
            ])

        assert result.exit_code == 0, result.output
        assert len(calls) == 1
        path, data, params, files = calls[0]
        assert path == "/api/product/update"
        assert params is None
        assert files is None
        assert data["id"] == "P001"
        assert data["name"] == "NewName"
        assert data["companyCarId"] == "CAR001"
        assert data["oemPrice"] == 12.5
        assert data["presale"] is True
        assert data["selfSupport"] is False
        assert data["newProduct"] is True
        assert data["weight"] == "01.20"
        assert data["volume"] == "10*20*30"
        assert data["rateNum"] == "001234"
        assert data["params"] == [{"paramId": "p1", "paramValue": "v1"}]
        assert "paramsJson" not in data
        assert data["extDataJson"] == '{"newEnergyAdapt":1}'
        assert data["mainVehicleModel"] == "主车型"
        assert data["referenceVehicleModel"] == "通用车型"
        assert data["suggestType"] == 1

    def test_product_update_rejects_non_array_params_json(self):
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.platform_service_cli as cli_module

        class FakeBackend:
            def post(self, path, data=None, params=None, files=None):
                return {"code": 200, "msg": "OK", "status": True, "data": None}

        runner = CliRunner()
        with mock.patch.object(cli_module, "Session") as mock_session, \
             mock.patch.object(cli_module, "PlatformServiceBackend", return_value=FakeBackend()):
            session = mock.MagicMock()
            session.base_url = "https://api.example.com/api/principal"
            session.token = "token"
            session.current_env = "test"
            mock_session.return_value = session

            result = runner.invoke(cli, [
                "--json", "product", "update",
                "--id", "P001",
                "--params-json", '{"paramId":"p1"}',
            ])

        assert result.exit_code != 0
        assert "--params-json 必须是 JSON 数组" in result.output

    def test_product_comment_calls_backend_endpoint(self):
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.platform_service_cli as cli_module

        calls = []

        class FakeBackend:
            def get(self, path, params=None):
                calls.append((path, params))
                return {"code": 200, "msg": "OK", "status": True, "data": []}

        runner = CliRunner()
        with mock.patch.object(cli_module, "Session") as mock_session, \
             mock.patch.object(cli_module, "PlatformServiceBackend", return_value=FakeBackend()):
            session = mock.MagicMock()
            session.base_url = "https://api.example.com/api/principal"
            session.token = "token"
            session.current_env = "test"
            mock_session.return_value = session

            result = runner.invoke(cli, ["--json", "product", "comment"])

        assert result.exit_code == 0, result.output
        assert calls == [("/api/product/comment", None)]


# ── Output format tests ───────────────────────────────────────────────

class TestOutputFormatting:
    """Test the output() function behavior."""
    def test_none_backend_module_loading(self):
        """Verify backend module can be imported correctly."""
        from cli_anything.platform_service.utils.backend import PlatformServiceBackend as B
        assert B is not None

    def test_cli_imports_all_commands(self):
        """Verify all 16 command groups + repl are registered."""
        from cli_anything.platform_service.platform_service_cli import cli
        cmds = list(cli.commands.keys())
        expected = [
            'product', 'company', 'user', 'inventory', 'shopping-cart',
            'price', 'quotation', 'purchase-order', 'stock-order',
            'menu', 'role', 'warehouse', 'product-category',
            'payment-term', 'statement', 'config', 'repl',
        ]
        for cmd in expected:
            assert cmd in cmds, f"Missing command: {cmd}"
        assert len(cmds) >= len(expected)

    def test_cli_command_callable(self):
        """Verify each command group is a valid Click group."""
        from cli_anything.platform_service.platform_service_cli import cli
        import click
        for name, cmd in cli.commands.items():
            assert isinstance(cmd, click.core.Group) or isinstance(cmd, click.core.Command), \
                f"{name} is not a Click command"

    def test_output_json_mode(self, capsys):
        """Test JSON output mode formatting."""
        import json
        import click
        data = {"code": 200, "msg": "OK", "status": True, "data": {"id": "123", "name": "test"}}
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
        captured = capsys.readouterr()
        # Should produce valid JSON output
        parsed = json.loads(captured.out.strip())
        assert parsed["code"] == 200
        assert parsed["data"]["name"] == "test"

    def test_session_module_standalone(self):
        """Session can be used without any backend dependency."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            s = Session(config_path=path)
            s.current_env = "test"
            s.base_url = "http://localhost"
            assert s.configured
            s.clear()
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ── backend-search retry chain tests ──────────────────────────────────

class TestSearchWithRetryChain:
    def _make_response(self, content):
        return {"code": 200, "msg": "OK", "status": True,
                "data": {"content": content, "totalElements": len(content), "totalPages": 1}}

    def test_first_attempt_hit_no_retry(self):
        """原始 keyword 命中时，只调用一次，matched_attempt 为原始keyword."""
        backend = mock.MagicMock()
        backend.get.return_value = self._make_response([{"id": "1", "name": "产品A"}])

        chain = _search_with_retry_chain(backend, "31110-RAA-A01")

        assert chain["matched_attempt"] == "原始keyword"
        assert len(chain["content"]) == 1
        assert chain["attempts"] == [{"label": "原始keyword", "keyword": "31110-RAA-A01", "count": 1}]
        backend.get.assert_called_once()

    def test_search_with_retry_chain_normalizes_oe(self):
        """原始 keyword 未命中，归一化(去横杠/空格/大写)后命中."""
        backend = mock.MagicMock()
        backend.get.side_effect = [
            self._make_response([]),  # 第1轮: 原始 keyword 为空
            self._make_response([{"id": "2", "name": "产品B"}]),  # 第2轮: 归一化命中
        ]

        chain = _search_with_retry_chain(backend, "31110 raa-a01")

        assert chain["matched_attempt"] == "归一化"
        assert len(chain["content"]) == 1
        assert chain["attempts"][0] == {"label": "原始keyword", "keyword": "31110 raa-a01", "count": 0}
        assert chain["attempts"][1]["label"] == "归一化"
        assert chain["attempts"][1]["keyword"] == "31110RAAA01"
        assert chain["attempts"][1]["count"] == 1
        assert backend.get.call_count == 2

    def test_search_with_retry_chain_core_8digit(self):
        """归一化仍未命中，但 keyword 为一代轴承格式时用核心8位重试."""
        backend = mock.MagicMock()
        backend.get.side_effect = [
            self._make_response([]),  # 第1轮: 原始 keyword 为空
            self._make_response([]),  # 第2轮: 归一化为空
            self._make_response([{"id": "3", "code": "DAC39720037"}]),  # 第3轮: 核心8位命中
        ]

        chain = _search_with_retry_chain(backend, "DAC39720037-2RZ(ABS88)")

        assert chain["matched_attempt"] == "核心8位"
        assert chain["attempts"][2] == {"label": "核心8位", "keyword": "39720037", "count": 1}
        assert backend.get.call_count == 3

    def test_search_with_retry_chain_all_miss(self):
        """所有轮次均未命中时 matched_attempt 为 None，content 为空."""
        backend = mock.MagicMock()
        backend.get.return_value = self._make_response([])

        chain = _search_with_retry_chain(backend, "NOTFOUND-123")

        assert chain["matched_attempt"] is None
        assert chain["content"] == []
        assert len(chain["attempts"]) == 2  # 原始keyword + 归一化 (非DAC格式无核心8位轮)


# ── backend-search/backend-detail 批量输入测试 ──────────────────────────

class TestBackendSearchBatch:
    def _make_response(self, content):
        return {"code": 200, "msg": "OK", "status": True,
                "data": {"content": content, "totalElements": len(content), "totalPages": 1}}

    def test_backend_search_batch_keywords(self):
        """--keywords 逗号分隔多个关键词，单进程复用 backend，分组输出."""
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.core.data_clean.backend_api as backend_api_module

        backend = mock.MagicMock()

        def fake_get(path, params=None):
            kw = params.get("keyword")
            if kw == "OE001":
                return self._make_response([{"id": "1", "name": "产品A", "oe": "OE001", "code": "C001"}])
            return self._make_response([{"id": "2", "name": "产品B", "oe": "OE002", "code": "C002"}])

        backend.get.side_effect = fake_get

        runner = CliRunner()
        with mock.patch.object(backend_api_module, "get_backend", return_value=backend) as mock_get_backend:
            result = runner.invoke(cli, ["data-clean", "backend-search", "--keywords", "OE001,OE002"])

        assert result.exit_code == 0, result.output
        mock_get_backend.assert_called_once()
        assert "=== 关键词: OE001 ===" in result.output
        assert "=== 关键词: OE002 ===" in result.output
        assert "产品A" in result.output
        assert "产品B" in result.output

    def test_backend_search_batch_keywords_json(self):
        """--keywords --json 输出 results 数组，每项含 keyword/content/matched_attempt."""
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.core.data_clean.backend_api as backend_api_module

        backend = mock.MagicMock()

        def fake_get(path, params=None):
            kw = params.get("keyword")
            if kw == "OE001":
                return self._make_response([{"id": "1", "name": "产品A"}])
            return self._make_response([])

        backend.get.side_effect = fake_get

        runner = CliRunner()
        with mock.patch.object(backend_api_module, "get_backend", return_value=backend):
            result = runner.invoke(cli, ["data-clean", "backend-search", "--keywords", "OE001,OE002", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "results" in data
        assert len(data["results"]) == 2
        assert data["results"][0]["keyword"] == "OE001"
        assert data["results"][0]["matched_attempt"] == "原始keyword"
        assert len(data["results"][0]["content"]) == 1
        assert data["results"][1]["keyword"] == "OE002"

    def test_backend_search_file_input(self):
        """--file 文件路径，每行一个关键词."""
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.core.data_clean.backend_api as backend_api_module

        backend = mock.MagicMock()
        backend.get.return_value = self._make_response([{"id": "1", "name": "产品X"}])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("OE001\nOE002\n")
            path = f.name

        try:
            runner = CliRunner()
            with mock.patch.object(backend_api_module, "get_backend", return_value=backend):
                result = runner.invoke(cli, ["data-clean", "backend-search", "--file", path])

            assert result.exit_code == 0, result.output
            assert "=== 关键词: OE001 ===" in result.output
            assert "=== 关键词: OE002 ===" in result.output
        finally:
            os.unlink(path)

    def test_backend_search_rejects_multiple_input_modes(self):
        """同时传入 --keyword 和 --keywords 应报错提示."""
        from cli_anything.platform_service.platform_service_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["data-clean", "backend-search", "--keyword", "OE001", "--keywords", "OE001,OE002"])

        assert result.exit_code != 0
        assert "--keyword" in result.output and "--keywords" in result.output

    def test_backend_search_requires_one_input(self):
        """三者均未传入应报错提示."""
        from cli_anything.platform_service.platform_service_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["data-clean", "backend-search"])

        assert result.exit_code != 0


class TestBackendDetailBatch:
    def _nums_response(self, items):
        return {"code": 200, "msg": "OK", "status": True, "data": {"items": items}}

    def _params_response(self, items):
        return {"code": 200, "msg": "OK", "status": True, "data": {"items": items}}

    def test_backend_detail_batch_product_ids(self):
        """--product-ids 逗号分隔多个产品ID，批量返回 results 字典."""
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.core.data_clean.backend_api as backend_api_module

        backend = mock.MagicMock()

        def fake_get(path, params=None):
            pid = params.get("productId")
            if path.endswith("/productNumDetail/list"):
                return self._nums_response([{"oe": f"OE-{pid}", "brand": "ZF"}])
            return self._params_response([{"paramName": "内径", "paramValue": "39"}])

        backend.get.side_effect = fake_get

        runner = CliRunner()
        with mock.patch.object(backend_api_module, "get_backend", return_value=backend) as mock_get_backend:
            result = runner.invoke(cli, ["data-clean", "backend-detail", "--product-ids", "P001,P002", "--json"])

        assert result.exit_code == 0, result.output
        mock_get_backend.assert_called_once()
        data = json.loads(result.output)
        assert "results" in data
        assert set(data["results"].keys()) == {"P001", "P002"}
        assert data["results"]["P001"]["related_numbers"][0]["oe"] == "OE-P001"
        assert data["results"]["P002"]["related_numbers"][0]["oe"] == "OE-P002"

    def test_backend_detail_batch_product_ids_human_readable(self):
        """--product-ids 人类可读模式按 product_id 分组打印."""
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.core.data_clean.backend_api as backend_api_module

        backend = mock.MagicMock()

        def fake_get(path, params=None):
            pid = params.get("productId")
            if path.endswith("/productNumDetail/list"):
                return self._nums_response([{"oe": f"OE-{pid}", "brand": "ZF"}])
            return self._params_response([])

        backend.get.side_effect = fake_get

        runner = CliRunner()
        with mock.patch.object(backend_api_module, "get_backend", return_value=backend):
            result = runner.invoke(cli, ["data-clean", "backend-detail", "--product-ids", "P001,P002"])

        assert result.exit_code == 0, result.output
        assert "=== 关键词: P001 ===" in result.output
        assert "=== 关键词: P002 ===" in result.output
        assert "OE-P001" in result.output
        assert "OE-P002" in result.output

    def test_backend_detail_rejects_multiple_input_modes(self):
        """同时传入 --product-id 和 --product-ids 应报错提示."""
        from cli_anything.platform_service.platform_service_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["data-clean", "backend-detail", "--product-id", "P001", "--product-ids", "P001,P002"])

        assert result.exit_code != 0
        assert "--product-id" in result.output and "--product-ids" in result.output

    def test_backend_detail_records_error_when_nums_resp_code_not_200(self):
        """productNumDetail/list 返回 code!=200 时，记录到 related_numbers_error，不影响 parameters 展示."""
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.core.data_clean.backend_api as backend_api_module

        backend = mock.MagicMock()

        def fake_get(path, params=None):
            if path.endswith("/productNumDetail/list"):
                return {"code": 500, "msg": "服务器内部错误", "status": False, "data": None}
            return self._params_response([{"paramName": "内径", "paramValue": "39"}])

        backend.get.side_effect = fake_get

        runner = CliRunner()
        with mock.patch.object(backend_api_module, "get_backend", return_value=backend):
            result = runner.invoke(cli, ["data-clean", "backend-detail", "--product-id", "P001", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "related_numbers_error" in data
        assert data["related_numbers_error"]["code"] == 500
        assert "related_numbers" not in data
        assert data["parameters"][0]["paramName"] == "内径"

    def test_backend_detail_records_error_when_params_resp_code_not_200(self):
        """productParamDetail/list 返回 code!=200 时，记录到 parameters_error，不影响 related_numbers 展示（人类可读模式）."""
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.core.data_clean.backend_api as backend_api_module

        backend = mock.MagicMock()

        def fake_get(path, params=None):
            if path.endswith("/productNumDetail/list"):
                return self._nums_response([{"oe": "OE-P001", "brand": "ZF"}])
            return {"code": 401, "msg": "未授权", "status": False, "data": None}

        backend.get.side_effect = fake_get

        runner = CliRunner()
        with mock.patch.object(backend_api_module, "get_backend", return_value=backend):
            result = runner.invoke(cli, ["data-clean", "backend-detail", "--product-id", "P001"])

        assert result.exit_code == 0, result.output
        assert "OE-P001" in result.output
        assert "参数查询失败" in result.output
        assert "401" in result.output


# ── classify_match 结构化 match_type/confidence 测试 ────────────────────

class TestClassifyMatch:
    def test_original_keyword_hit_is_exact_oe_high(self):
        """backend-search 第1轮(原始keyword)命中 → exact_oe/high."""
        assert classify_match("原始keyword", None) == {"match_type": "exact_oe", "confidence": "high"}

    def test_normalized_hit_is_normalized_oe_medium(self):
        """backend-search 第2轮(归一化)命中 → normalized_oe/medium."""
        assert classify_match("归一化", None) == {"match_type": "normalized_oe", "confidence": "medium"}

    def test_core_8digit_hit_is_core_8digit_medium(self):
        """backend-search 第3轮(核心8位)命中 → core_8digit/medium."""
        assert classify_match("核心8位", None) == {"match_type": "core_8digit", "confidence": "medium"}

    def test_no_attempt_hit_is_none(self):
        """backend-search 全部未命中 (matched_attempt=None) → none/none."""
        assert classify_match(None, None) == {"match_type": "none", "confidence": "none"}

    def test_oe_query_oe_input_with_result_is_exact_oe_high(self):
        """oe-query: 输入类型为 OE 号且第三方有结果 → exact_oe/high."""
        assert classify_match("oe", True) == {"match_type": "exact_oe", "confidence": "high"}

    def test_oe_query_dac_input_with_result_is_fuzzy_low(self):
        """oe-query: 输入类型为 DAC 编码且第三方有结果 → fuzzy/low."""
        assert classify_match("dac", True) == {"match_type": "fuzzy", "confidence": "low"}

    def test_oe_query_dimension_input_with_result_is_fuzzy_low(self):
        """oe-query: 输入类型为尺寸且第三方有结果 → fuzzy/low."""
        assert classify_match("dimension", True) == {"match_type": "fuzzy", "confidence": "low"}

    def test_oe_query_input_with_no_result_is_none(self):
        """oe-query: 第三方查询无任何结果 → none/none，无论输入类型."""
        assert classify_match("oe", False) == {"match_type": "none", "confidence": "none"}
        assert classify_match("dac", False) == {"match_type": "none", "confidence": "none"}
        assert classify_match("dimension", False) == {"match_type": "none", "confidence": "none"}


# ── backend-search --json 附加 match_type/confidence 字段测试 ───────────

class TestBackendSearchMatchTypeFields:
    def _make_response(self, content):
        return {"code": 200, "msg": "OK", "status": True,
                "data": {"content": content, "totalElements": len(content), "totalPages": 1}}

    def test_single_keyword_json_includes_match_type_exact_oe(self):
        """--keyword --json: 第1轮命中 → 附加 match_type=exact_oe/confidence=high."""
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.core.data_clean.backend_api as backend_api_module

        backend = mock.MagicMock()
        backend.get.return_value = self._make_response([{"id": "1", "name": "产品A"}])

        runner = CliRunner()
        with mock.patch.object(backend_api_module, "get_backend", return_value=backend):
            result = runner.invoke(cli, ["data-clean", "backend-search", "--keyword", "31110-RAA-A01", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["matched_attempt"] == "原始keyword"
        assert data["match_type"] == "exact_oe"
        assert data["confidence"] == "high"
        # 现有字段不受影响
        assert data["data"]["content"][0]["name"] == "产品A"

    def test_single_keyword_json_includes_match_type_normalized(self):
        """--keyword --json: 第2轮(归一化)命中 → 附加 match_type=normalized_oe/confidence=medium."""
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.core.data_clean.backend_api as backend_api_module

        backend = mock.MagicMock()
        backend.get.side_effect = [
            self._make_response([]),
            self._make_response([{"id": "2", "name": "产品B"}]),
        ]

        runner = CliRunner()
        with mock.patch.object(backend_api_module, "get_backend", return_value=backend):
            result = runner.invoke(cli, ["data-clean", "backend-search", "--keyword", "31110 raa-a01", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["matched_attempt"] == "归一化"
        assert data["match_type"] == "normalized_oe"
        assert data["confidence"] == "medium"

    def test_single_keyword_json_all_miss_includes_none(self):
        """--keyword --json: 全部未命中 → 附加 match_type=none/confidence=none."""
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.core.data_clean.backend_api as backend_api_module

        backend = mock.MagicMock()
        backend.get.return_value = self._make_response([])

        runner = CliRunner()
        with mock.patch.object(backend_api_module, "get_backend", return_value=backend):
            result = runner.invoke(cli, ["data-clean", "backend-search", "--keyword", "NOTFOUND-123", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["matched_attempt"] is None
        assert data["match_type"] == "none"
        assert data["confidence"] == "none"

    def test_batch_keywords_json_includes_match_type_per_result(self):
        """--keywords --json: 每个结果项均附加 match_type/confidence."""
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.core.data_clean.backend_api as backend_api_module

        backend = mock.MagicMock()

        def fake_get(path, params=None):
            kw = params.get("keyword")
            if kw == "OE001":
                return self._make_response([{"id": "1", "name": "产品A"}])
            return self._make_response([])

        backend.get.side_effect = fake_get

        runner = CliRunner()
        with mock.patch.object(backend_api_module, "get_backend", return_value=backend):
            result = runner.invoke(cli, ["data-clean", "backend-search", "--keywords", "OE001,OE002", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["results"][0]["match_type"] == "exact_oe"
        assert data["results"][0]["confidence"] == "high"
        # OE002: 原始keyword + 归一化(OE002归一化后与原始相同，不会重试) 均未命中
        assert data["results"][1]["match_type"] == "none"
        assert data["results"][1]["confidence"] == "none"


# ── 第三方查询结果本地缓存 (cache.py) 测试 ──────────────────────────────

class TestCache:
    def test_cache_key_deterministic_and_length(self):
        """_cache_key 对相同输入返回相同的24位结果，不同输入结果不同."""
        k1 = _cache_key("tecalliance", "45840045")
        k2 = _cache_key("tecalliance", "45840045")
        k3 = _cache_key("tecalliance", "45840046")

        assert k1 == k2
        assert len(k1) == 24
        assert k1 != k3

    def test_set_and_get_cached_round_trip(self, tmp_path, monkeypatch):
        """set_cached 写入后, get_cached 能取回相同 value 且未过期."""
        monkeypatch.setattr(cache_module, "CACHE_DIR", str(tmp_path))

        set_cached("tecalliance", "45840045", value=[{"brand": "SKF", "oes": ["123"]}])
        record = get_cached("tecalliance", "45840045")

        assert record is not None
        assert record["value"] == [{"brand": "SKF", "oes": ["123"]}]
        assert "ts" in record

    def test_get_cached_returns_none_when_missing(self, tmp_path, monkeypatch):
        """缓存文件不存在时返回 None."""
        monkeypatch.setattr(cache_module, "CACHE_DIR", str(tmp_path))

        assert get_cached("tecalliance", "NOTCACHED") is None

    def test_get_cached_returns_none_when_expired(self, tmp_path, monkeypatch):
        """超过 ttl 的缓存视为未命中，返回 None."""
        monkeypatch.setattr(cache_module, "CACHE_DIR", str(tmp_path))

        set_cached("tecalliance", "45840045", value=["data"])
        record = get_cached("tecalliance", "45840045")
        # 手动将写入时间戳改写为很久以前
        path = cache_module._cache_path("tecalliance", "45840045")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"value": record["value"], "ts": record["ts"] - 1000}, f)

        assert get_cached("tecalliance", "45840045", ttl=100) is None
        # ttl 足够大时仍命中
        assert get_cached("tecalliance", "45840045", ttl=100000) is not None

    def test_cache_stored_under_namespace_subdir(self, tmp_path, monkeypatch):
        """缓存文件按 CACHE_DIR/namespace/{key}.json 存储."""
        monkeypatch.setattr(cache_module, "CACHE_DIR", str(tmp_path))

        set_cached("17vin", "31110-RAA-A01", value={"oes": []})

        key = _cache_key("31110-RAA-A01")
        expected_path = tmp_path / "17vin" / f"{key}.json"
        assert expected_path.exists()


# ── oe-query 缓存集成测试 ────────────────────────────────────────────────

class TestOeQueryCache:
    def test_oe_query_second_call_hits_cache_skips_search(self, tmp_path, monkeypatch):
        """第二次相同查询命中缓存, search_tecalliance 不再被调用, 结果标注 from_cache."""
        from cli_anything.platform_service.platform_service_cli import cli
        import cli_anything.platform_service.core.data_clean.oe_query as oe_query_module

        monkeypatch.setattr(cache_module, "CACHE_DIR", str(tmp_path))

        with mock.patch.object(
            oe_query_module, "search_tecalliance",
            return_value=[{"brand": "SKF", "oes": ["123456"], "vehicles": []}],
        ) as mock_search, \
                mock.patch.object(oe_query_module, "search_17vin",
                                  return_value={"oes": [], "brand_parts": [], "vehicles": []}):
            runner = CliRunner()

            result1 = runner.invoke(
                cli, ["--json", "data-clean", "oe-query", "--query", "45840045", "--skip-17vin"])
            assert result1.exit_code == 0, result1.output
            data1 = json.loads(result1.stdout)
            assert data1["from_cache"] is False
            assert mock_search.call_count == 1

            result2 = runner.invoke(
                cli, ["--json", "data-clean", "oe-query", "--query", "45840045", "--skip-17vin"])
            assert result2.exit_code == 0, result2.output
            data2 = json.loads(result2.stdout)
            assert data2["from_cache"] is True
            assert data2["tecalliance"] == data1["tecalliance"]
            # 缓存命中，底层搜索函数未被再次调用
            assert mock_search.call_count == 1
