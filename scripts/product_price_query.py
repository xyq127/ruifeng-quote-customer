#!/usr/bin/env python3
"""根据编号/OE 查询睿锋平台售价 salePrice（客户版，走 /inventory/list）。

薄封装：复用本目录自包含模块 ruifeng_platform，无需安装 RayForm-CLI。
等价于 `python ruifeng_platform.py price ...`，保留此入口便于向后兼容。

客户版只暴露售价（salePrice），不输出采购价 / P1 / P2 / P3。

用法:
  python product_price_query.py --keyword 30BG05S5G-2DST --json
  python product_price_query.py --keywords 30BG05S5G-2DST,DAC30600337
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ruifeng_platform import get_client, query_sale_price  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="根据编号/OE 查询睿锋平台售价 salePrice")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--keyword", help="单个编号/OE")
    group.add_argument("--keywords", help="多个编号/OE，逗号分隔")
    parser.add_argument("--product-id", help="可选：命中多条时优先匹配该产品行")
    parser.add_argument("--query-type", dest="query_type", default="ENCODE")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    kws = [args.keyword.strip()] if args.keyword else \
        [k.strip() for k in args.keywords.split(",") if k.strip()]

    try:
        client = get_client()
    except RuntimeError as exc:
        sys.exit(str(exc))
    if not client.token:
        sys.exit("未登录或 token 缺失，请先执行：python ruifeng_platform.py login --mobile <手机号>")
    rows = [query_sale_price(client, kw, product_id=args.product_id,
                             query_type=args.query_type) for kw in kws]

    if args.json:
        out = rows[0] if (args.keyword and len(rows) == 1) else {"results": rows}
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            v = r.get("salePrice")
            print(f"{r['keyword']} 售价: {'—' if v is None else v}")
            if r.get("errors"):
                print(f"  ⚠️ {'; '.join(r['errors'])}")


if __name__ == "__main__":
    main()
