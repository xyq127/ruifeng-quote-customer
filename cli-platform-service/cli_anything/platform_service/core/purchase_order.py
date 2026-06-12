"""采购单管理命令."""

import click
from ..platform_service_cli import get_backend, output


@click.group()
def purchase_order():
    """采购单管理"""
    pass


# ========== 供应商采购单 ==========


@click.group()
def po_supplier():
    """供应商采购单"""
    pass


@po_supplier.command(name="list")
@click.option("--status", help="状态")
@click.option("--warehouse-id", help="仓库ID")
@click.option("--supplier-id", help="供应商ID")
@click.option("--salesman-id", help="业务员ID")
@click.option("--id", help="采购单ID")
@click.option("--page", type=int, help="页码")
@click.option("--size", type=int, help="每页条数")
def po_supplier_list(status, warehouse_id, supplier_id, salesman_id, id, page, size):
    """获取供应商采购单列表"""
    backend = get_backend()
    params = {}
    if status:
        params["status"] = status
    if warehouse_id:
        params["warehouseId"] = warehouse_id
    if supplier_id:
        params["supplierId"] = supplier_id
    if salesman_id:
        params["salesmanId"] = salesman_id
    if id:
        params["id"] = id
    if page is not None:
        params["page"] = page
    if size is not None:
        params["size"] = size
    result = backend.get("/api/purchaseOrder/supplier/list", params=params)
    output(result)


@po_supplier.command(name="get")
@click.option("--id", required=True, help="采购单ID")
def po_supplier_get(id):
    """获取采购单详情"""
    backend = get_backend()
    result = backend.get("/api/purchaseOrder/findById", params={"id": id})
    output(result)


@po_supplier.command(name="create")
@click.option("--warehouse-id", required=True, help="仓库ID")
@click.option("--company-id", required=True, help="公司ID")
@click.option("--remark", help="备注")
@click.option("--detail-json", required=True, help="明细 JSON，如 [{\"productId\":\"x\",\"planCount\":5}]")
def po_supplier_create(warehouse_id, company_id, remark, detail_json):
    """创建供应商采购单"""
    backend = get_backend()
    data = {
        "warehouseId": warehouse_id,
        "companyId": company_id,
        "detailJson": detail_json,
    }
    if remark:
        data["remark"] = remark
    result = backend.post("/api/purchaseOrder/supplier/purchase", data=data)
    output(result)


@po_supplier.command(name="template")
def po_supplier_template():
    """下载供应商采购单导入模板"""
    backend = get_backend()
    result = backend.get("/api/purchaseOrder/supplier/export/template")
    output(result)


# ========== 客户采购单 ==========


@click.group()
def po_customer():
    """客户采购单"""
    pass


@po_customer.command(name="list")
@click.option("--status", help="状态")
@click.option("--warehouse-id", help="仓库ID")
@click.option("--company-id", help="公司ID")
@click.option("--pre-sale", type=bool, help="是否预售")
@click.option("--salesman-id", help="业务员ID")
@click.option("--page", type=int, help="页码")
@click.option("--size", type=int, help="每页条数")
def po_customer_list(status, warehouse_id, company_id, pre_sale, salesman_id, page, size):
    """获取客户采购单列表"""
    backend = get_backend()
    params = {}
    if status:
        params["status"] = status
    if warehouse_id:
        params["warehouseId"] = warehouse_id
    if company_id:
        params["companyId"] = company_id
    if pre_sale is not None:
        params["preSale"] = pre_sale
    if salesman_id:
        params["salesmanId"] = salesman_id
    if page is not None:
        params["page"] = page
    if size is not None:
        params["size"] = size
    result = backend.get("/api/purchaseOrder/customer/list", params=params)
    output(result)


@po_customer.command(name="get")
@click.option("--id", required=True, help="采购单ID")
def po_customer_get(id):
    """获取采购单详情"""
    backend = get_backend()
    result = backend.get("/api/purchaseOrder/findById", params={"id": id})
    output(result)


@po_customer.command(name="create")
@click.option("--company-id", help="公司ID")
@click.option("--province", help="省份")
@click.option("--city", help="城市")
@click.option("--county", help="区县")
@click.option("--detail-address", help="详细地址")
@click.option("--receiver", help="收货人")
@click.option("--mobile", help="手机号")
@click.option("--remark", help="备注")
@click.option("--logistics-name", help="物流名称")
@click.option("--detail-json", required=True, help="明细 JSON")
def po_customer_create(company_id, province, city, county, detail_address, receiver, mobile, remark, logistics_name, detail_json):
    """创建客户采购单"""
    backend = get_backend()
    data = {"detailJson": detail_json}
    if company_id:
        data["companyId"] = company_id
    if province:
        data["province"] = province
    if city:
        data["city"] = city
    if county:
        data["county"] = county
    if detail_address:
        data["detailAddress"] = detail_address
    if receiver:
        data["receiver"] = receiver
    if mobile:
        data["mobile"] = mobile
    if remark:
        data["remark"] = remark
    if logistics_name:
        data["logisticsName"] = logistics_name
    result = backend.post("/api/purchaseOrder/customer/purchase", data=data)
    output(result)


# ========== 注册子命令组 ==========

purchase_order.add_command(po_supplier, name="supplier")
purchase_order.add_command(po_customer, name="customer")


# ========== 顶级命令 ==========


@purchase_order.command(name="cancel")
@click.option("--id", required=True, help="采购单ID")
def purchase_order_cancel(id):
    """取消采购单"""
    backend = get_backend()
    result = backend.post("/api/purchaseOrder/delete", data={"id": id})
    output(result)


@purchase_order.command(name="comment")
def purchase_order_comment():
    """获取评论"""
    backend = get_backend()
    result = backend.get("/api/purchaseOrder/comment")
    output(result)
