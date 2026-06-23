#!/usr/bin/env python3
"""17vin EPC 自包含客户端 —— OE 互换 / 品牌件 / 车型查询，无需安装 RayForm-CLI。

17vin 是纯 HTTP API（`http://api.17vin.com:8080`，MD5 token 鉴权），
与睿锋平台同属「HTTP 查询层」，因此一并内置到本 skill，仅依赖标准库 + requests。
泰安联是浏览器（Playwright/CDP）方式，不在此模块内，仍走 CLI。

凭据解析顺序（**不在分发的 skill 里硬编码账号**）：
  1. 环境变量 17VIN_USERNAME / 17VIN_PASSWORD / 17VIN_API
  2. 配置文件 ~/.cli-anything-platform-service/config.json 的 "vin17" 段
     （与睿锋共用同一文件，可用 RUIFENG_CONFIG 覆盖路径）
  3. 都没有 → 报错并提示如何设置

子命令:
  config-set   写入 17vin 用户名/密码/api_base 到配置（文件 0o600）
  config-show  查看 17vin 凭据状态（密码打码）
  oe           OE 互换 + 品牌件 + 车型（三步链：search_epc→interchange→modellist）
  parts        按 OE 反查配件（search_epc）
  vehicle      按车型关键词搜索

用法示例:
  python vin17_epc.py config-set --username <用户名> --password <密码>
  python vin17_epc.py oe --oe 90363-45050 --json
  python vin17_epc.py vehicle --keyword 长安CS75
"""

import argparse
import getpass
import hashlib
import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ruifeng_platform import (  # noqa: E402
    load_config, save_config, CONFIG_FILE, first_run_hint,
)


DEFAULT_API = "http://api.17vin.com:8080"
# 17vin 接口固定的鉴权 query 字段名（接口契约字段，非密钥）
_AUTH_PARAM = "token"
# 反查互换时认定为「大厂关联编号」的品牌（与 CLI 对齐）
MAJOR_BRANDS = {"SKF", "NSK", "FAG", "INA", "NTN", "KOYO", "TIMKEN", "SNR"}


# ── 凭据解析 ──────────────────────────────────────────────────────────

def resolve_credentials(cfg: dict):
    """返回 (api_base, username, password)；env 优先，其次 config 的 vin17 段。"""
    v = cfg.get("vin17", {}) if isinstance(cfg.get("vin17"), dict) else {}
    api = os.environ.get("17VIN_API") or v.get("api_base") or DEFAULT_API
    user = os.environ.get("17VIN_USERNAME") or v.get("username")
    pwd = os.environ.get("17VIN_PASSWORD") or v.get("password")
    return api.rstrip("/"), user, pwd


def _request_signature(username: str, password: str, url_params: str = "") -> str:
    """17vin 官方请求签名算法：md5(md5(user) + md5(pwd) + url_params)。"""
    u = hashlib.md5(username.encode()).hexdigest()
    p = hashlib.md5(password.encode()).hexdigest()
    return hashlib.md5(f"{u}{p}{url_params}".encode()).hexdigest()


# ── 客户端 ────────────────────────────────────────────────────────────

class Vin17Client:
    """17vin EPC HTTP 客户端。token 按 url_params 现算，无登录态。"""

    def __init__(self, api_base, username, password):
        if not username or not password:
            raise RuntimeError(first_run_hint("17vin 用户名+密码"))
        self.api_base = api_base.rstrip("/")
        self.username = username
        self.password = password
        self.session = requests.Session()

    def _call(self, url_params: str, retries: int = 2, timeout: int = 15) -> dict:
        """按官方约定附加 user + 请求签名后 GET；失败重试，最终失败返回 {"code": -1}。"""
        sig = _request_signature(self.username, self.password, url_params)
        url = f"{self.api_base}{url_params}"
        # 官方约定的鉴权 query 参数名（"token" 为接口固定字段名，非密钥本身）
        auth = {"user": self.username, _AUTH_PARAM: sig}  # 由 requests 拼到 query 末尾
        for _ in range(retries):
            try:
                r = self.session.get(url, params=auth,
                                     headers={"User-Agent": "Mozilla/5.0"},
                                     timeout=timeout)
                return r.json()
            except Exception:  # noqa: BLE001 — 与 CLI 一致：失败即重试/降级
                time.sleep(0.5)
        return {"code": -1}

    # ── 高层查询 ──────────────────────────────────────────────────────

    def search_parts_by_oe(self, oe: str) -> list:
        """OE 反查配件（action=search_epc）。长安/铃木/众泰/日产不支持。"""
        r = self._call(f"/?action=search_epc&query_part_number={oe}"
                       f"&query_match_type=smart")
        return r.get("data", []) if r.get("code") == 1 else []

    def search_vehicle(self, keyword: str) -> list:
        """按车型关键词搜索（action=models，series=keyword）。"""
        r = self._call(f"/?action=models&series={keyword}")
        return r.get("data", []) if r.get("code") == 1 else []

    def search_oe_interchange(self, oe: str) -> dict:
        """OE 互换 + 大厂品牌件 + 车型：search_epc→interchange→modellist 三步链。"""
        result = {"oe": oe, "oes": [], "brand_parts": [], "vehicles": []}

        # Step 1: 4001 search_epc → 取 Group_id
        r1 = self._call(f"/?action=search_epc&query_part_number={oe}"
                        f"&query_match_type=smart")
        if r1.get("code") != 1 or not r1.get("data"):
            return result
        group_id = (r1["data"][0] or {}).get("Group_id", "")
        if not group_id:
            return result

        time.sleep(0.3)

        # Step 2: 4004 互换号 + 工厂件
        r2 = self._call(
            f"/?action=get_interchange_from_part_number_and_group_id_plus_zh"
            f"&part_number={oe}&group_id={group_id}")
        if r2.get("code") == 1:
            ii = (r2.get("data", {}) or {}).get("InterchangeInfo", {}) or {}
            for item in (ii.get("OeInterchange", []) or []):
                for p in (item.get("Part_number", ""),
                          item.get("Replacement_part_number", "")):
                    p = (p or "").strip()
                    if p and p != oe:
                        result["oes"].append(p)
            for item in (ii.get("FactoryInterchange", []) or []):
                brand = (item.get("Brand_name_en", "") or "").strip()
                pn = (item.get("Part_number", "") or "").strip()
                if brand.upper() in MAJOR_BRANDS and pn:
                    result["brand_parts"].append(f"{brand}:{pn}")

        time.sleep(0.3)

        # Step 3: 40031 车型列表
        r3 = self._call(
            f"/?action=get_modellist_from_part_number_and_group_id"
            f"&part_number={oe}&group_id={group_id}")
        if r3.get("code") == 1:
            models = [m.get("Detail", "") for m in
                      ((r3.get("data", {}) or {}).get("ModelListStd", []) or [])
                      if m.get("Detail")]
            result["vehicles"] = models[:10]

        # 去重保序
        result["oes"] = list(dict.fromkeys(result["oes"]))
        result["brand_parts"] = list(dict.fromkeys(result["brand_parts"]))
        return result


# ── 构造与高层入口 ────────────────────────────────────────────────────

def get_client() -> Vin17Client:
    api, user, pwd = resolve_credentials(load_config())
    return Vin17Client(api, user, pwd)


def query_17vin_oe(oe: str) -> dict:
    """供工作流复用：返回 {oe, oes[], brand_parts[], vehicles[]}。"""
    return get_client().search_oe_interchange(oe)


# ── 子命令 ────────────────────────────────────────────────────────────

def cmd_config_set(args):
    cfg = load_config()
    v = cfg.setdefault("vin17", {})
    if args.api_base:
        v["api_base"] = args.api_base
    if args.username:
        v["username"] = args.username
    if not args.no_password:
        pwd = args.password or os.environ.get("17VIN_PASSWORD") or getpass.getpass("17vin 密码: ")
        if pwd:
            v["password"] = pwd
    save_config(cfg)
    print(f"17vin 凭据已写入 {CONFIG_FILE}")


def cmd_config_show(args):
    api, user, pwd = resolve_credentials(load_config())
    masked = (pwd[:1] + "***" + pwd[-1:]) if pwd and len(pwd) > 2 else ("***" if pwd else "(未设置)")
    print(f"配置文件: {CONFIG_FILE}")
    print(f"api_base : {api}")
    print(f"username : {user or '(未设置)'}")
    print(f"password : {masked}")


def cmd_oe(args):
    result = get_client().search_oe_interchange(args.oe)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(f"OE [{args.oe}] 17vin 查询:")
    print(f"  互换 OE ({len(result['oes'])}): {', '.join(result['oes']) or '—'}")
    print(f"  大厂关联件 ({len(result['brand_parts'])}): "
          f"{', '.join(result['brand_parts']) or '—'}")
    print(f"  适配车型 ({len(result['vehicles'])}):")
    for m in result["vehicles"]:
        print(f"    - {m}")


def cmd_parts(args):
    rows = get_client().search_parts_by_oe(args.oe)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print(f"OE [{args.oe}] 配件 ({len(rows)} 条):")
        for r in rows[:10]:
            print(f"  {r}")


def cmd_vehicle(args):
    rows = get_client().search_vehicle(args.keyword)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    print(f"车型 [{args.keyword}] ({len(rows)} 条):")
    for v in rows[:20]:
        vid = v.get("modelId", v.get("id", ""))
        brand = v.get("brandName", v.get("brand", ""))
        series = v.get("seriesName", v.get("series", ""))
        year = v.get("year", "")
        print(f"  [{vid}] {brand} {series} ({year})")


def build_parser():
    p = argparse.ArgumentParser(description="17vin EPC 自包含客户端（OE 互换 / 车型）")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("config-set", help="写入 17vin 凭据")
    s.add_argument("--username")
    s.add_argument("--password", help="不传则交互式安全输入")
    s.add_argument("--api-base")
    s.add_argument("--no-password", action="store_true", help="仅更新用户名/api，不动密码")
    s.set_defaults(func=cmd_config_set)

    s = sub.add_parser("config-show", help="查看 17vin 凭据状态")
    s.set_defaults(func=cmd_config_show)

    s = sub.add_parser("oe", help="OE 互换 + 品牌件 + 车型（三步链）")
    s.add_argument("--oe", required=True)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_oe)

    s = sub.add_parser("parts", help="按 OE 反查配件")
    s.add_argument("--oe", required=True)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_parts)

    s = sub.add_parser("vehicle", help="按车型关键词搜索")
    s.add_argument("--keyword", required=True)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_vehicle)

    return p


def main():
    args = build_parser().parse_args()
    try:
        args.func(args)
    except RuntimeError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
