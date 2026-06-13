"""Platform Service API Backend Client.

Wraps REST API calls to the platform-service Spring Boot backend.
Handles authentication, error handling, and response parsing.
"""

import os
import socket
import requests
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from .no_sni_adapter import NoSNIHTTPSAdapter

# 正式环境域名 → 服务器 IP（用于绕过 SNI 阻断时的直连目标）
_HOST_IP_MAP = {
    'rfscm.com': '8.155.164.3',
}


def _direct_connect_ok(host: str, port: int = 443, timeout: float = 2.0) -> bool:
    """快速探测是否能直连并完成 TLS 握手（不经代理）。

    部分网络环境下 TCP 三次握手可以成功，但携带 SNI 的 TLS ClientHello
    发出后无响应（被丢弃），因此仅测 TCP connect 不够，需测到 TLS 握手。
    """
    import ssl as _ssl
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            ctx = _ssl.create_default_context()
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                ssock.do_handshake()
        return True
    except (OSError, _ssl.SSLError):
        return False


class PlatformServiceBackend:
    """HTTP client for the platform-service REST API."""

    def __init__(self, base_url: str, token: Optional[str] = None,
                 credentials: Optional[Dict[str, str]] = None,
                 on_token_refresh=None):
        self.base_url = base_url.rstrip('/')
        self.token = token
        # credentials: {"mobile": ..., "password": ...}，提供后 401 时自动重新登录
        self.credentials = credentials
        # 自动重登成功后回调持久化新 token（如写回 config.json）
        self.on_token_refresh = on_token_refresh
        self.session = requests.Session()
        host = urlparse(self.base_url).hostname
        scheme = urlparse(self.base_url).scheme
        if host in {'rfscm.com', '8.155.167.214', '8.155.164.3'}:
            if scheme == 'https':
                proxy = os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')
                if _direct_connect_ok(host):
                    # 正式环境通过域名直连，不走系统代理（代理会破坏 SSL CONNECT 握手）
                    self.session.trust_env = False
                elif proxy and host in _HOST_IP_MAP:
                    # 本机直连不通：部分网络环境下，代理对 SNI=rfscm.com 的连接
                    # 会被重置 (SSL_ERROR_SYSCALL)。改为经代理连接服务器 IP，
                    # TLS 握手时不发送 SNI，但仍校验证书链与 hostname (SAN)。
                    parsed_proxy = urlparse(proxy)
                    proxy_addr = (parsed_proxy.hostname, parsed_proxy.port or 80)
                    self.session.mount(
                        'https://',
                        NoSNIHTTPSAdapter(host_ip_map=_HOST_IP_MAP, proxy=proxy_addr),
                    )
                    self.session.trust_env = False
                else:
                    self.session.trust_env = False
            # 测试环境用 HTTP，但在 WSL 下需要系统代理才能访问 IP
            # trust_env 默认 True，代理会自动处理 HTTP 转发
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        if token:
            self.headers['Authorization'] = f'Bearer {token}'

    def set_token(self, token: str):
        """Update the bearer token."""
        self.token = token
        self.headers['Authorization'] = f'Bearer {token}'

    def login(self, mobile: Optional[str] = None, password: Optional[str] = None,
              timeout: int = 30) -> Dict[str, Any]:
        """登录获取新 token 并更新到当前实例.

        参数缺省时使用实例化传入的 credentials。
        登录端点位于网关根路径（scheme://host/api/oauth/login/customer），
        不带 base_url 中的 /api/principal 服务前缀。

        Returns:
            登录响应的 data 字典（含 token、nickName 等）。

        Raises:
            RuntimeError: 凭据缺失、网络错误或登录失败。
        """
        creds = self.credentials or {}
        mobile = (mobile or creds.get('mobile') or '').strip()
        password = password or creds.get('password')
        if not mobile or not password:
            raise RuntimeError("缺少登录凭据（mobile/password）")

        parsed = urlparse(self.base_url)
        login_url = f"{parsed.scheme}://{parsed.netloc}/api/oauth/login/customer"
        try:
            resp = self.session.post(login_url,
                                     data={"mobile": mobile, "password": password},
                                     headers={"Accept": "application/json"},
                                     timeout=timeout)
            resp.raise_for_status()
            body = resp.json()
        except requests.exceptions.Timeout:
            raise RuntimeError(f"登录超时（{timeout}秒），请检查网络连接")
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"无法连接到 {login_url}")
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            raise RuntimeError(f"登录失败（HTTP {status}），请检查手机号和密码")
        except ValueError:
            raise RuntimeError("登录失败: 服务器返回异常响应")

        if body.get("code") != 200 or not body.get("status"):
            raise RuntimeError(f"登录失败: {body.get('msg', '未知错误')}")
        data = body.get("data")
        token = data.get("token") if isinstance(data, dict) else None
        if not token or not isinstance(token, str) or len(token) < 20:
            raise RuntimeError("登录失败: 服务器未返回有效 token")

        self.set_token(token)
        if self.on_token_refresh:
            try:
                self.on_token_refresh(token)
            except Exception:
                pass
        return data

    def _request(self, method: str, path: str, params: Dict = None,
                 data: Dict = None, files: Dict = None,
                 timeout: int = 30, _retry: bool = True) -> Dict[str, Any]:
        """Send a request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: API path relative to base URL (e.g., "/api/product/list").
            params: URL query parameters.
            data: JSON request body.
            files: Multipart file uploads.
            timeout: Request timeout in seconds.

        Returns:
            Parsed JSON response.

        Raises:
            RuntimeError: On connection error, auth failure, or HTTP error.
        """
        # Strip base_url's path prefix from request path to avoid duplication.
        # e.g. base_url="https://rfscm.com/api/principal" + path="/api/product/list"
        #   → /api/principal is in base_url, strip /api from path → /product/list
        #   → final: https://rfscm.com/api/principal/product/list
        if path.startswith('/api/principal/'):
            path = path[len('/api/principal'):]
        elif path.startswith('/api/'):
            path = path[len('/api'):]
        url = f"{self.base_url}{path}"

        try:
            if method.upper() == 'GET':
                response = self.session.get(url, headers=self.headers,
                                            params=params, timeout=timeout)
            elif method.upper() == 'POST':
                if files:
                    # multipart/form-data 请求不能固定 Content-Type:
                    # application/json，否则服务端会返回 415。去掉该 header，
                    # 交由 requests 根据 files 自动生成带 boundary 的
                    # multipart/form-data Content-Type。
                    multipart_headers = {k: v for k, v in self.headers.items()
                                          if k.lower() != 'content-type'}
                    response = self.session.post(url, headers=multipart_headers,
                                                 data=data, files=files, timeout=timeout)
                else:
                    response = self.session.post(url, headers=self.headers,
                                                 params=params, json=data, timeout=timeout)
            elif method.upper() == 'PUT':
                response = self.session.put(url, headers=self.headers,
                                            json=data, timeout=timeout)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, headers=self.headers,
                                               params=params, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            if response.status_code == 204:
                return {"code": 204, "msg": "操作成功", "status": True, "data": None}

            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                return response.json()
            else:
                return {"code": 200, "msg": "OK", "status": True,
                        "data": {"content_type": content_type,
                                 "size": len(response.content)}}

        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"无法连接到平台服务: {self.base_url}\n"
                f"请确认:\n"
                f"1. 平台服务已启动\n"
                f"2. Base URL 正确\n"
                f"3. 网络连接正常"
            )
        except requests.exceptions.HTTPError as e:
            resp = e.response
            if resp is not None:
                if resp.status_code == 401:
                    # 已保存账号密码时自动重新登录并重试一次
                    if _retry and self.credentials:
                        try:
                            self.login()
                        except RuntimeError as login_err:
                            raise RuntimeError(
                                f"认证失败: Token 已过期，自动重新登录失败 — {login_err}")
                        return self._request(method, path, params=params,
                                             data=data, files=files,
                                             timeout=timeout, _retry=False)
                    raise RuntimeError("认证失败: Token 无效或已过期")
                elif resp.status_code == 403:
                    raise RuntimeError("权限不足")
                elif resp.status_code == 404:
                    raise RuntimeError(f"资源不存在: {path}")
                else:
                    raise RuntimeError(f"HTTP 错误 {resp.status_code}: {resp.text[:500]}")
            else:
                raise RuntimeError(f"HTTP 错误: {e}")
        except requests.exceptions.Timeout:
            raise RuntimeError("请求超时，请检查网络连接")
        except Exception as e:
            raise RuntimeError(f"请求失败: {e}")

    def get(self, path: str, params: Dict = None) -> Dict[str, Any]:
        """Send GET request."""
        return self._request('GET', path, params=params)

    def post(self, path: str, data: Dict = None, params: Dict = None,
             files: Dict = None) -> Dict[str, Any]:
        """Send POST request."""
        return self._request('POST', path, data=data, params=params, files=files)

    def put(self, path: str, data: Dict = None) -> Dict[str, Any]:
        """Send PUT request."""
        return self._request('PUT', path, data=data)

    def delete(self, path: str, params: Dict = None) -> Dict[str, Any]:
        """Send DELETE request."""
        return self._request('DELETE', path, params=params)

    def validate_connection(self) -> bool:
        """Test connectivity by fetching the first page of products."""
        try:
            self.get("/api/product/list", params={"page": 1, "size": 1})
            return True
        except Exception:
            return False
