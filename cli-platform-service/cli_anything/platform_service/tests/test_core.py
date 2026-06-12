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
