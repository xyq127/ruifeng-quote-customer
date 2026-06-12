"""用户管理"""

import click
from ..platform_service_cli import get_backend, output


@click.group()
def user():
    """用户管理"""
    pass


@user.command(name="list")
@click.option("--nick-name", help="用户昵称")
@click.option("--mobile", help="手机号")
@click.option("--page", default=1, type=int, help="页码")
@click.option("--size", default=15, type=int, help="每页条数")
def user_list(nick_name, mobile, page, size):
    """获取用户列表"""
    backend = get_backend()
    params = {"page": page, "size": size}
    if nick_name:
        params["nickName"] = nick_name
    if mobile:
        params["mobile"] = mobile
    result = backend.get("/api/user/list", params=params)
    output(result)


@user.command(name="get")
@click.option("--id", required=True, help="用户ID")
def user_get(id):
    """根据ID获取用户详情"""
    backend = get_backend()
    result = backend.get("/api/user/findById", params={"id": id})
    output(result)


@user.command(name="create")
@click.option("--nick-name", required=True, help="用户昵称")
@click.option("--mobile", required=True, help="手机号")
@click.option("--sex", help="性别")
def user_create(nick_name, mobile, sex):
    """创建用户"""
    backend = get_backend()
    data = {
        "nickName": nick_name,
        "mobile": mobile,
    }
    if sex:
        data["sex"] = sex
    result = backend.post("/api/user/add", json=data)
    output(result)


@user.command(name="update")
@click.option("--id", required=True, help="用户ID")
@click.option("--nick-name", help="用户昵称")
@click.option("--mobile", help="手机号")
@click.option("--sex", help="性别")
def user_update(id, nick_name, mobile, sex):
    """更新用户信息"""
    backend = get_backend()
    data = {"id": id}
    if nick_name:
        data["nickName"] = nick_name
    if mobile:
        data["mobile"] = mobile
    if sex:
        data["sex"] = sex
    result = backend.post("/api/user/update", json=data)
    output(result)


@user.command(name="bind-wecom")
@click.option("--user-id", required=True, help="用户ID")
@click.option("--we-com", required=True, help="企业微信ID")
def user_bind_wecom(user_id, we_com):
    """绑定企业微信"""
    backend = get_backend()
    data = {
        "userId": user_id,
        "weCom": we_com,
    }
    result = backend.post("/api/user/bindWeCom", json=data)
    output(result)


@user.command(name="comment")
def user_comment():
    """获取用户备注"""
    backend = get_backend()
    result = backend.get("/api/user/comment")
    output(result)
