"""角色管理"""

import click
from ..platform_service_cli import get_backend, output


@click.group()
def role():
    """角色管理"""
    pass


@role.command(name="list")
@click.option("--role-name", help="角色名称")
@click.option("--role-code", help="角色编码")
@click.option("--page", default=1, type=int, help="页码")
@click.option("--size", default=15, type=int, help="每页条数")
def role_list(role_name, role_code, page, size):
    """获取角色列表"""
    backend = get_backend()
    params = {"page": page, "size": size}
    if role_name:
        params["roleName"] = role_name
    if role_code:
        params["roleCode"] = role_code
    result = backend.get("/api/role/list", params=params)
    output(result)


@role.command(name="all")
def role_all():
    """获取全部角色"""
    backend = get_backend()
    result = backend.get("/api/role/all")
    output(result)


@role.command(name="get")
@click.option("--id", required=True, help="角色ID")
def role_get(id):
    """获取角色详情"""
    backend = get_backend()
    result = backend.get("/api/role/findById", params={"id": id})
    output(result)


@role.command(name="create")
@click.option("--role-name", required=True, help="角色名称")
@click.option("--role-code", required=True, help="角色编码")
@click.option("--description", help="角色描述")
def role_create(role_name, role_code, description):
    """创建角色"""
    backend = get_backend()
    data = {"roleName": role_name, "roleCode": role_code}
    if description:
        data["description"] = description
    result = backend.post("/api/role/add", data=data)
    output(result)


@role.command(name="update")
@click.option("--id", required=True, help="角色ID")
@click.option("--role-name", help="角色名称")
@click.option("--role-code", help="角色编码")
@click.option("--description", help="角色描述")
def role_update(id, role_name, role_code, description):
    """更新角色"""
    backend = get_backend()
    data = {"id": id}
    if role_name:
        data["roleName"] = role_name
    if role_code:
        data["roleCode"] = role_code
    if description:
        data["description"] = description
    result = backend.post("/api/role/update", data=data)
    output(result)


@role.command(name="delete")
@click.option("--id", required=True, help="角色ID")
def role_delete(id):
    """删除角色"""
    backend = get_backend()
    data = {"id": id}
    result = backend.post("/api/role/delete", data=data)
    output(result)


@role.command(name="comment")
def role_comment():
    """查看角色管理模块备注"""
    backend = get_backend()
    result = backend.get("/api/role/comment")
    output(result)
