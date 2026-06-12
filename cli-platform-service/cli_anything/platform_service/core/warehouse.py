"""仓库管理"""

import click
from ..platform_service_cli import get_backend, output


@click.group()
def warehouse():
    """仓库管理"""
    pass


@warehouse.command(name="list")
def warehouse_list():
    """获取仓库列表"""
    backend = get_backend()
    result = backend.get("/api/warehouse/list")
    output(result)


@warehouse.command(name="goods")
def warehouse_goods():
    """获取仓库货品"""
    backend = get_backend()
    result = backend.get("/api/warehouse/goods")
    output(result)


@warehouse.command(name="get")
@click.option("--id", required=True, help="仓库ID")
def warehouse_get(id):
    """获取仓库详情"""
    backend = get_backend()
    result = backend.get("/api/warehouse/findById", params={"id": id})
    output(result)


@warehouse.command(name="create")
@click.option("--name", required=True, help="仓库名称")
@click.option("--type", "type_", type=int, required=True, default=0, help="仓库类型: 0默认")
@click.option("--contact", help="联系人")
@click.option("--phone", help="联系电话")
@click.option("--province", help="省份")
@click.option("--city", help="城市")
@click.option("--county", help="区县")
@click.option("--detail-address", help="详细地址")
@click.option("--main", is_flag=True, help="是否主仓库")
def warehouse_create(name, type_, contact, phone, province, city, county, detail_address, main):
    """创建仓库"""
    backend = get_backend()
    data = {"name": name, "type": type_, "main": main}
    if contact:
        data["contact"] = contact
    if phone:
        data["phone"] = phone
    if province:
        data["province"] = province
    if city:
        data["city"] = city
    if county:
        data["county"] = county
    if detail_address:
        data["detailAddress"] = detail_address
    result = backend.post("/api/warehouse/save", data=data)
    output(result)


@warehouse.command(name="update")
@click.option("--id", required=True, help="仓库ID")
@click.option("--name", required=True, help="仓库名称")
@click.option("--contact", help="联系人")
@click.option("--phone", help="联系电话")
@click.option("--province", help="省份")
@click.option("--city", help="城市")
@click.option("--county", help="区县")
@click.option("--detail-address", help="详细地址")
@click.option("--main", type=bool, required=True, help="是否主仓库")
@click.option("--status", type=int, required=True, help="状态")
def warehouse_update(id, name, contact, phone, province, city, county, detail_address, main, status):
    """更新仓库"""
    backend = get_backend()
    data = {"id": id, "name": name, "main": main, "status": status}
    if contact:
        data["contact"] = contact
    if phone:
        data["phone"] = phone
    if province:
        data["province"] = province
    if city:
        data["city"] = city
    if county:
        data["county"] = county
    if detail_address:
        data["detailAddress"] = detail_address
    result = backend.post("/api/warehouse/update", data=data)
    output(result)


@warehouse.command(name="delete")
@click.option("--id", required=True, help="仓库ID")
def warehouse_delete(id):
    """删除仓库"""
    backend = get_backend()
    data = {"id": id}
    result = backend.post("/api/warehouse/delete", data=data)
    output(result)


@warehouse.command(name="comment")
def warehouse_comment():
    """查看仓库管理模块备注"""
    backend = get_backend()
    result = backend.get("/api/warehouse/comment")
    output(result)
