#!/usr/bin/env python3
"""根据产品 ID 查询睿锋平台四个价格（采购价 / P1 / P2 / P3）。

薄封装：复用本目录自包含模块 ruifeng_platform，无需安装 RayForm-CLI。
等价于 `python ruifeng_platform.py price ...`，保留此入口便于向后兼容。

用法:
  python product_price_query.py --product-id 123 --json
  python product_price_query.py --product-ids 123,456
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ruifeng_platform import get_client, query_prices  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="根据产品 ID 查询睿锋平台四个价格")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--product-id", help="单个产品 ID")
    group.add_argument("--product-ids", help="多个产品 ID，逗号分隔")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    ids = [args.product_id.strip()] if args.product_id else \
        [p.strip() for p in args.product_ids.split(",") if p.strip()]

    try:
        client = get_client()
    except RuntimeError as exc:
        sys.exit(str(exc))
    if not client.token:
        sys.exit("未登录或 token 缺失，请先执行：python ruifeng_platform.py login --mobile <手机号>")
    rows = [query_prices(client, pid) for pid in ids]

    if args.json:
        out = rows[0] if (args.product_id and len(rows) == 1) else {"results": rows}
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        labels = [("采购价", "purchasePrice"), ("OEM价格(P1)", "p1Price"),
                  ("品牌一级销售价(P2)", "p2Price"), ("品牌二级销售价(P3)", "p3Price")]
        for r in rows:
            print(f"产品 {r['productId']} 价格:")
            for name, key in labels:
                v = r.get(key)
                print(f"  {name}: {'—' if v is None else v}")
            if r.get("errors"):
                print(f"  ⚠️ {'; '.join(r['errors'])}")
            print()


if __name__ == "__main__":
    main()
