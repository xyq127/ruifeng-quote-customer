"""报价单管理命令."""

import click
from ..platform_service_cli import get_backend, output


@click.group()
def quotation():
    """报价单管理"""
    pass


@quotation.command(name="list")
@click.option("--page", type=int, help="页码")
@click.option("--size", type=int, help="每页条数")
def quotation_list(page, size):
    """获取报价单列表"""
    backend = get_backend()
    params = {}
    if page is not None:
        params["page"] = page
    if size is not None:
        params["size"] = size
    result = backend.get("/api/quotation/list", params=params)
    output(result)


@quotation.command(name="get")
@click.option("--id", required=True, help="报价单ID")
def quotation_get(id):
    """获取报价单详情"""
    backend = get_backend()
    result = backend.get("/api/quotation/findById", params={"id": id})
    output(result)


@quotation.command(name="create")
@click.option("--cart-ids", required=True, help="购物车ID列表，逗号分隔")
def quotation_create(cart_ids):
    """创建报价单"""
    backend = get_backend()
    ids_list = [cid.strip() for cid in cart_ids.split(",") if cid.strip()]
    result = backend.post("/api/quotation/save", json=ids_list)
    output(result)


@quotation.command(name="delete")
@click.option("--id", required=True, help="报价单ID")
def quotation_delete(id):
    """删除报价单"""
    backend = get_backend()
    result = backend.delete("/api/quotation/delete", params={"id": id})
    output(result)


@quotation.command(name="comment")
def quotation_comment():
    """获取评论"""
    backend = get_backend()
    result = backend.get("/api/quotation/comment")
    output(result)
