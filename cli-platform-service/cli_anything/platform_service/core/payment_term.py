"""付款条件管理"""

import json
import click
from ..platform_service_cli import get_backend, output


@click.group()
def payment_term():
    """付款条件管理"""
    pass


@payment_term.command(name="list")
@click.option("--page", default=1, type=int, help="页码")
@click.option("--size", default=15, type=int, help="每页条数")
def pt_list(page, size):
    """获取付款条件列表"""
    backend = get_backend()
    result = backend.get("/api/paymentTerm/list", params={"page": page, "size": size})
    output(result)


@payment_term.command(name="all")
def pt_all():
    """获取全部付款条件"""
    backend = get_backend()
    result = backend.get("/api/paymentTerm/all")
    output(result)


@payment_term.command(name="get")
@click.option("--id", required=True, help="付款条件ID")
def pt_get(id):
    """根据ID获取付款条件详情"""
    backend = get_backend()
    result = backend.get("/api/paymentTerm/findById", params={"id": id})
    output(result)


@payment_term.command(name="create")
@click.option("--data-json", required=True, help="JSON 格式的付款条件数据")
def pt_create(data_json):
    """创建付款条件"""
    backend = get_backend()
    data = json.loads(data_json)
    result = backend.post("/api/paymentTerm/save", data=data)
    output(result)


@payment_term.command(name="update")
@click.option("--data-json", required=True, help="JSON 格式的付款条件数据(须含id)")
def pt_update(data_json):
    """更新付款条件"""
    backend = get_backend()
    data = json.loads(data_json)
    result = backend.post("/api/paymentTerm/update", data=data)
    output(result)


@payment_term.command(name="delete")
@click.option("--id", required=True, help="付款条件ID")
def pt_delete(id):
    """删除付款条件"""
    backend = get_backend()
    result = backend.post("/api/paymentTerm/delete", data={"id": id})
    output(result)


@payment_term.command(name="comment")
def pt_comment():
    """获取付款条件备注"""
    backend = get_backend()
    result = backend.get("/api/paymentTerm/comment")
    output(result)
