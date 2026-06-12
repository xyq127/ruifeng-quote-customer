"""出入库管理"""

import click
from ..platform_service_cli import get_backend, output


@click.group()
def stock_order():
    """出入库管理"""
    pass


@stock_order.command(name="list")
@click.option("--ref-id", help="关联订单ID")
@click.option("--id", help="出入库单ID")
@click.option("--type", "type_", type=int, required=True, default=0, help="类型: 0采购入库 1其他入库 2盘盈入库 3退货入库 4调拨入库")
@click.option("--warehouse-id", help="仓库ID")
@click.option("--posting", is_flag=True, help="是否已过账")
@click.option("--company-id", help="公司ID")
@click.option("--pre-sale", is_flag=True, help="是否预售")
@click.option("--page", default=1, type=int, help="页码")
@click.option("--size", default=15, type=int, help="每页条数")
def stock_order_list(ref_id, id, type_, warehouse_id, posting, company_id, pre_sale, page, size):
    """获取出入库单列表"""
    backend = get_backend()
    params = {"type": type_, "page": page, "size": size}
    if ref_id:
        params["refId"] = ref_id
    if id:
        params["id"] = id
    if warehouse_id:
        params["warehouseId"] = warehouse_id
    if posting:
        params["posting"] = "true"
    if company_id:
        params["companyId"] = company_id
    if pre_sale:
        params["preSale"] = "true"
    result = backend.get("/api/stockOrder/list", params=params)
    output(result)


@stock_order.command(name="get")
@click.option("--id", required=True, help="出入库单ID")
def stock_order_get(id):
    """获取出入库单详情"""
    backend = get_backend()
    result = backend.get("/api/stockOrder/findById", params={"id": id})
    output(result)


@stock_order.command(name="purchase-in")
@click.option("--company-id", required=True, help="公司ID")
@click.option("--warehouse-id", required=True, help="仓库ID")
@click.option("--detail-json", required=True, help="入库明细JSON, 格式: [{\"id\":\"x\",\"actualCount\":5}]")
def stock_order_purchase_in(company_id, warehouse_id, detail_json):
    """采购入库"""
    backend = get_backend()
    data = {
        "companyId": company_id,
        "warehouseId": warehouse_id,
        "detailJson": detail_json,
    }
    result = backend.post("/api/stockOrder/purchase_in", data=data)
    output(result)


@stock_order.command(name="order-out")
@click.option("--ref-id", required=True, help="关联订单ID")
def stock_order_order_out(ref_id):
    """订单出库"""
    backend = get_backend()
    data = {"refId": ref_id}
    result = backend.post("/api/stockOrder/order_out", data=data)
    output(result)


@stock_order.command(name="set-location")
@click.option("--id", required=True, help="出入库单ID")
@click.option("--details", required=True, help="货位明细JSON, 格式: [{\"locationNum\":\"A01-01\",\"quantity\":5}]")
def stock_order_set_location(id, details):
    """设置货位"""
    backend = get_backend()
    data = {"id": id, "details": details}
    result = backend.post("/api/stockOrder/setLocation", data=data)
    output(result)


@stock_order.command(name="post")
def stock_order_post():
    """过账"""
    backend = get_backend()
    result = backend.post("/api/stockOrder/posting")
    output(result)


@stock_order.command(name="delete")
@click.option("--id", required=True, help="出入库单ID")
def stock_order_delete(id):
    """删除出入库单"""
    backend = get_backend()
    data = {"id": id}
    result = backend.post("/api/stockOrder/delete", data=data)
    output(result)


@stock_order.command(name="comment")
def stock_order_comment():
    """查看出入库管理模块备注"""
    backend = get_backend()
    result = backend.get("/api/stockOrder/comment")
    output(result)
