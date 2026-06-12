"""菜单管理"""

import json

import click
from ..platform_service_cli import get_backend, output


@click.group()
def menu():
    """菜单管理"""
    pass


@menu.command(name="list")
def menu_list():
    """获取菜单列表"""
    backend = get_backend()
    result = backend.get("/api/menu/list")
    output(result)


@menu.command(name="update")
@click.option("--data-json", required=True, help="菜单更新数据JSON字符串")
def menu_update(data_json):
    """更新菜单"""
    backend = get_backend()
    data = json.loads(data_json)
    result = backend.post("/api/menu/update", data=data)
    output(result)


@menu.command(name="comment")
def menu_comment():
    """查看菜单管理模块备注"""
    backend = get_backend()
    result = backend.get("/api/menu/comment")
    output(result)
