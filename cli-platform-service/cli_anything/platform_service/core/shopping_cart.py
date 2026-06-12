"""购物车管理命令."""

import click
from ..platform_service_cli import get_backend, output


@click.group()
def shopping_cart():
    """购物车管理"""
    pass


@shopping_cart.command(name="list")
@click.option("--company-id", help="公司ID")
@click.option("--warehouse-id", help="仓库ID")
def shopping_cart_list(company_id, warehouse_id):
    """获取购物车列表"""
    backend = get_backend()
    params = {}
    if company_id:
        params["companyId"] = company_id
    if warehouse_id:
        params["warehouseId"] = warehouse_id
    result = backend.get("/api/shoppingCart/list", params=params)
    output(result)


@shopping_cart.command(name="add")
@click.option("--inventory-id", required=True, help="库存ID")
@click.option("--quantity", required=True, type=int, help="数量")
@click.option("--company-id", help="公司ID")
def shopping_cart_add(inventory_id, quantity, company_id):
    """添加商品到购物车"""
    backend = get_backend()
    data = {"inventoryId": inventory_id, "quantity": quantity}
    if company_id:
        data["companyId"] = company_id
    result = backend.post("/api/shoppingCart/save", data=data)
    output(result)


@shopping_cart.command(name="get")
@click.option("--id", required=True, help="购物车条目ID")
def shopping_cart_get(id):
    """获取购物车条目详情"""
    backend = get_backend()
    result = backend.get("/api/shoppingCart/findById", params={"id": id})
    output(result)


@shopping_cart.command(name="update")
@click.option("--id", required=True, help="购物车条目ID")
@click.option("--quantity", required=True, type=int, help="新数量")
def shopping_cart_update(id, quantity):
    """更新购物车条目数量"""
    backend = get_backend()
    data = {"id": id, "quantity": quantity}
    result = backend.post("/api/shoppingCart/update", data=data)
    output(result)


@shopping_cart.command(name="delete")
@click.option("--id", required=True, help="购物车条目ID")
def shopping_cart_delete(id):
    """删除购物车条目"""
    backend = get_backend()
    result = backend.delete("/api/shoppingCart/delete", params={"id": id})
    output(result)


@shopping_cart.command(name="batch-delete")
@click.option("--ids", required=True, help="购物车条目ID列表，逗号分隔")
def shopping_cart_batch_delete(ids):
    """批量删除购物车条目"""
    backend = get_backend()
    result = backend.delete("/api/shoppingCart/batchDelete", params={"ids": ids})
    output(result)


@shopping_cart.command(name="count")
@click.option("--company-id", help="公司ID")
def shopping_cart_count(company_id):
    """获取购物车商品数量"""
    backend = get_backend()
    params = {}
    if company_id:
        params["companyId"] = company_id
    result = backend.get("/api/shoppingCart/count", params=params)
    output(result)


@shopping_cart.command(name="comment")
def shopping_cart_comment():
    """获取评论"""
    backend = get_backend()
    result = backend.get("/api/shoppingCart/comment")
    output(result)
