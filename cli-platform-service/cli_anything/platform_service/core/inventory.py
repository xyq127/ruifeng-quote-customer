"""库存管理"""

import click
from ..platform_service_cli import get_backend, output


@click.group()
def inventory():
    """库存管理"""
    pass


@inventory.command(name="list")
@click.option("--keyword", help="搜索关键词")
@click.option("--supplier-id", help="供应商ID")
@click.option("--presale", help="是否预售")
@click.option("--self-support", help="是否自营")
@click.option("--new-product", help="是否新品")
@click.option("--tax", help="税率")
@click.option("--post", help="邮费")
@click.option("--warehouse-id", help="仓库ID")
@click.option("--category", help="分类")
@click.option("--brand", help="品牌")
@click.option("--car", help="适用车型")
@click.option("--gte-price", type=float, help="最低价格")
@click.option("--lte-price", type=float, help="最高价格")
@click.option("--page", default=1, type=int, help="页码")
@click.option("--size", default=15, type=int, help="每页条数")
def inventory_list(keyword, supplier_id, presale, self_support, new_product, tax, post, warehouse_id, category, brand, car, gte_price, lte_price, page, size):
    """获取库存列表"""
    backend = get_backend()
    params = {"page": page, "size": size}
    if keyword:
        params["keyword"] = keyword
    if supplier_id:
        params["supplierId"] = supplier_id
    if presale:
        params["presale"] = presale
    if self_support:
        params["selfSupport"] = self_support
    if new_product:
        params["newProduct"] = new_product
    if tax:
        params["tax"] = tax
    if post:
        params["post"] = post
    if warehouse_id:
        params["warehouseId"] = warehouse_id
    if category:
        params["category"] = category
    if brand:
        params["brand"] = brand
    if car:
        params["car"] = car
    if gte_price is not None:
        params["gtePrice"] = gte_price
    if lte_price is not None:
        params["ltePrice"] = lte_price
    result = backend.get("/api/inventory/list", params=params)
    output(result)


@inventory.command(name="get")
@click.option("--id", required=True, help="库存ID")
def inventory_get(id):
    """根据ID获取库存详情"""
    backend = get_backend()
    result = backend.get("/api/inventory/findById", params={"id": id})
    output(result)


@inventory.command(name="delete")
@click.option("--id", required=True, help="库存ID")
def inventory_delete(id):
    """删除库存"""
    backend = get_backend()
    result = backend.post("/api/inventory/delete", json={"id": id})
    output(result)


@inventory.command(name="sync")
def inventory_sync():
    """同步库存"""
    backend = get_backend()
    result = backend.post("/api/inventory/snyc")
    output(result)


@inventory.command(name="comment")
def inventory_comment():
    """获取库存备注"""
    backend = get_backend()
    result = backend.get("/api/inventory/comment")
    output(result)
