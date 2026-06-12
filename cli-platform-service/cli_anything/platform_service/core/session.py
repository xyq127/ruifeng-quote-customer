"""Session management for the platform-service CLI.

Handles configuration persistence (base URL, token) with atomic file locking.
Supports multiple environments (test, prod) with switchable current_env.
"""

import os
import json
import fcntl

from pathlib import Path
from typing import Dict, Any, Optional


DEFAULT_CONFIG_DIR = Path.home() / ".cli-anything-platform-service"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"

# Pre-configured environment server IPs (project-specific)
_ENV_SERVERS = {
    "test": "8.155.167.214",
    "prod": "8.155.164.3",
}


def _locked_save_json(path: str, data: dict, **dump_kwargs) -> None:
    """Atomically write JSON with exclusive file locking."""
    try:
        f = open(path, "r+")
    except FileNotFoundError:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        f = open(path, "w")
    with f:
        locked = False
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            locked = True
        except (ImportError, OSError):
            pass
        try:
            f.seek(0)
            f.truncate()
            json.dump(data, f, **dump_kwargs)
            f.flush()
            # 配置中可能含登录密码，仅限本用户读写
            os.chmod(path, 0o600)
        finally:
            if locked:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _load_json(path: str) -> dict:
    """Load JSON with shared lock."""
    try:
        f = open(path, "r")
    except FileNotFoundError:
        return {}
    with f:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        except (ImportError, OSError):
            pass
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


class Session:
    """Session configuration manager with multi-environment support.

    Config file structure:
        {
            "current_env": "test",
            "environments": {
                "test": {"base_url": "...", "token": "..."},
                "prod": {"base_url": "...", "token": "..."}
            }
        }

    Properties base_url/token delegate to the current environment.
    """

    KNOWN_ENVS = list(_ENV_SERVERS.keys())  # ["test", "prod"]

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or str(DEFAULT_CONFIG_FILE)
        self._config = _load_json(self.config_path)
        # Ensure environments key exists
        if "environments" not in self._config:
            self._config["environments"] = {}

    # ── current_env ───────────────────────────────────────────────────

    @property
    def current_env(self) -> Optional[str]:
        """Currently active environment name (test / prod)."""
        return self._config.get("current_env") or os.environ.get("PLATFORM_ENV")

    @current_env.setter
    def current_env(self, value: str):
        if value and value not in self.KNOWN_ENVS:
            raise ValueError(f"未知环境: {value}，已知: {', '.join(self.KNOWN_ENVS)}")
        self._config["current_env"] = value
        self._save()

    # ── Per-env config access ─────────────────────────────────────────

    def _env_config(self, env: Optional[str] = None) -> dict:
        env = env or self.current_env
        if not env:
            return {}
        return self._config.setdefault("environments", {}).setdefault(env, {})

    @property
    def base_url(self) -> Optional[str]:
        """Base URL for the current environment."""
        env = self.current_env
        if env:
            url = self._env_config(env).get("base_url")
            if url:
                return url
        return os.environ.get("PLATFORM_BASE_URL")

    @base_url.setter
    def base_url(self, value: str):
        env = self.current_env
        if not env:
            raise RuntimeError("请先设置当前环境 (config use <env>)")
        self._env_config(env)["base_url"] = value
        self._save()

    @property
    def token(self) -> Optional[str]:
        """Bearer token for the current environment."""
        env = self.current_env
        if env:
            tok = self._env_config(env).get("token")
            if tok:
                return tok
        return os.environ.get("PLATFORM_TOKEN")

    @token.setter
    def token(self, value: str):
        env = self.current_env
        if not env:
            raise RuntimeError("请先设置当前环境 (config use <env>)")
        self._env_config(env)["token"] = value
        self._save()

    @property
    def mobile(self) -> Optional[str]:
        """登录手机号（当前环境），用于 token 过期自动重新登录."""
        env = self.current_env
        if env:
            val = self._env_config(env).get("mobile")
            if val:
                return val
        return os.environ.get("PLATFORM_MOBILE")

    @mobile.setter
    def mobile(self, value: str):
        env = self.current_env
        if not env:
            raise RuntimeError("请先设置当前环境 (config use <env>)")
        self._env_config(env)["mobile"] = value
        self._save()

    @property
    def password(self) -> Optional[str]:
        """登录密码（当前环境），用于 token 过期自动重新登录."""
        env = self.current_env
        if env:
            val = self._env_config(env).get("password")
            if val:
                return val
        return os.environ.get("PLATFORM_PASSWORD")

    @password.setter
    def password(self, value: str):
        env = self.current_env
        if not env:
            raise RuntimeError("请先设置当前环境 (config use <env>)")
        self._env_config(env)["password"] = value
        self._save()

    @property
    def configured(self) -> bool:
        return bool(self.current_env and self.base_url)

    # ── Environment helpers ───────────────────────────────────────────

    def get_env_server(self, env: str) -> Optional[str]:
        """Get the pre-configured server IP for an environment."""
        return _ENV_SERVERS.get(env)

    def env_configured(self, env: str) -> bool:
        """Check if a specific environment has base_url configured."""
        return bool(self._env_config(env).get("base_url"))

    def list_envs(self) -> Dict[str, Dict[str, Any]]:
        """Return all environments with their config status."""
        result = {}
        for name in self.KNOWN_ENVS:
            cfg = self._env_config(name)
            server = _ENV_SERVERS.get(name, "未知")
            result[name] = {
                "server": server,
                "base_url": cfg.get("base_url"),
                "has_token": bool(cfg.get("token")),
                "is_current": name == self.current_env,
            }
        return result

    # ── Persistence ───────────────────────────────────────────────────

    def _save(self):
        _locked_save_json(self.config_path, self._config, indent=2, ensure_ascii=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_env": self.current_env,
            "base_url": self.base_url,
            "token": "***" if self.token else None,
            "config_path": str(self.config_path),
            "environments": self.list_envs(),
        }

    def clear(self, env: Optional[str] = None):
        """Clear config for a specific env, or all config if env is None."""
        if env:
            self._config.setdefault("environments", {}).pop(env, None)
            if self._config.get("current_env") == env:
                self._config["current_env"] = None
            self._save()
        else:
            self._config = {"environments": {}}
            if os.path.exists(self.config_path):
                os.remove(self.config_path)
