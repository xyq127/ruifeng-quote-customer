"""HTTPS 适配器：经代理连接但不发送 TLS SNI 扩展。

背景：
某些网络环境下，代理出口对 TLS ClientHello 中 SNI 字段等于特定域名
（如 rfscm.com）的连接会被重置 (SSL_ERROR_SYSCALL / Connection reset)，
但相同的连接如果不携带 SNI（即直接用 IP 建立 TLS）则可以正常握手。

本模块通过：
1. 经 HTTP CONNECT 代理隧道连接到目标服务器 IP；
2. TLS 握手时 server_hostname=None（不发送 SNI 扩展）；
3. 握手后手动校验证书的 subjectAltName 是否包含目标域名，
   保证证书校验强度与正常 SNI 握手一致。

仅对配置的 host->ip 映射生效，其余请求走 requests 默认逻辑。
"""

import io
import socket
import ssl
import http.client
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter


class NoSNIHTTPSConnection(http.client.HTTPSConnection):
    """不发送 SNI 的 HTTPS 连接，证书校验仍按 hostname (SAN) 进行。"""

    def __init__(self, host: str, port: int, ip: str,
                 proxy: Optional[Tuple[str, int]] = None, **kwargs):
        super().__init__(host, port, **kwargs)
        self._target_ip = ip
        self._proxy = proxy

    def connect(self):
        if self._proxy:
            sock = socket.create_connection(self._proxy, timeout=self.timeout)
            sock.sendall(
                f"CONNECT {self._target_ip}:{self.port} HTTP/1.1\r\n"
                f"Host: {self._target_ip}:{self.port}\r\n\r\n".encode()
            )
            resp_line = b""
            while b"\r\n\r\n" not in resp_line:
                chunk = sock.recv(1)
                if not chunk:
                    break
                resp_line += chunk
            if b"200" not in resp_line.split(b"\r\n")[0]:
                raise ConnectionError(f"代理 CONNECT 失败: {resp_line[:200]!r}")
        else:
            sock = socket.create_connection((self._target_ip, self.port), timeout=self.timeout)

        ctx = ssl.create_default_context()
        ctx.check_hostname = False  # server_hostname=None 时必须关闭，改为下面手动校验
        ctx.verify_mode = ssl.CERT_REQUIRED
        ssock = ctx.wrap_socket(sock, server_hostname=None)

        cert = ssock.getpeercert()
        san = [v for k, v in cert.get('subjectAltName', ()) if k == 'DNS']
        if self.host not in san:
            ssock.close()
            raise ssl.SSLCertVerificationError(
                f"证书 hostname 不匹配: 期望 {self.host}, 证书SAN={san}")

        self.sock = ssock


class NoSNIHTTPSAdapter(HTTPAdapter):
    """对 host_ip_map 中的域名，经代理(可选)连接服务器 IP 且不发送 SNI。

    Args:
        host_ip_map: {域名: 服务器IP}，仅命中映射的域名走特殊逻辑。
        proxy: (proxy_host, proxy_port)，None 表示不经代理直连 IP。
    """

    def __init__(self, host_ip_map: Dict[str, str],
                 proxy: Optional[Tuple[str, int]] = None, *args, **kwargs):
        self.host_ip_map = host_ip_map
        self.proxy = proxy
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        parsed = urlparse(request.url)
        if parsed.scheme != "https" or parsed.hostname not in self.host_ip_map:
            return super().send(request, **kwargs)

        ip = self.host_ip_map[parsed.hostname]
        port = parsed.port or 443
        timeout = kwargs.get("timeout") or 30
        if isinstance(timeout, tuple):
            timeout = max(timeout)

        try:
            conn = NoSNIHTTPSConnection(parsed.hostname, port, ip,
                                         proxy=self.proxy, timeout=timeout)
            conn.connect()
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
            headers = dict(request.headers)
            headers.setdefault("Host", parsed.hostname)
            conn.request(request.method, path, body=request.body, headers=headers)
            httpresp = conn.getresponse()
            body = httpresp.read()
        except (OSError, ssl.SSLError, ConnectionError) as e:
            raise requests.exceptions.ConnectionError(e, request=request)

        resp = requests.Response()
        resp.status_code = httpresp.status
        resp.headers.update(httpresp.getheaders())
        resp.raw = io.BytesIO(body)
        resp._content = body
        resp.url = request.url
        resp.request = request
        resp.encoding = requests.utils.get_encoding_from_headers(resp.headers)
        return resp
