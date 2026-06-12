"""对账单管理"""

import click
from ..platform_service_cli import get_backend, output


@click.group()
def statement():
    """对账单管理"""
    pass


@statement.command(name="supplier")
@click.option("--page", default=1, type=int, help="页码")
@click.option("--size", default=15, type=int, help="每页条数")
@click.option("--supplier-id", help="供应商ID")
@click.option("--status", help="对账状态")
@click.option("--start-date", help="开始日期")
@click.option("--end-date", help="结束日期")
def st_supplier(page, size, supplier_id, status, start_date, end_date):
    """获取供应商对账单列表"""
    backend = get_backend()
    params = {"page": page, "size": size}
    if supplier_id:
        params["supplierId"] = supplier_id
    if status:
        params["status"] = status
    if start_date:
        params["startDate"] = start_date
    if end_date:
        params["endDate"] = end_date
    result = backend.get("/api/statement/supplier", params=params)
    output(result)


@statement.command(name="customer")
@click.option("--page", default=1, type=int, help="页码")
@click.option("--size", default=15, type=int, help="每页条数")
@click.option("--customer-id", help="客户ID")
@click.option("--status", help="对账状态")
@click.option("--start-date", help="开始日期")
@click.option("--end-date", help="结束日期")
def st_customer(page, size, customer_id, status, start_date, end_date):
    """获取客户对账单列表"""
    backend = get_backend()
    params = {"page": page, "size": size}
    if customer_id:
        params["customerId"] = customer_id
    if status:
        params["status"] = status
    if start_date:
        params["startDate"] = start_date
    if end_date:
        params["endDate"] = end_date
    result = backend.get("/api/statement/customer", params=params)
    output(result)


@statement.command(name="get")
@click.option("--id", required=True, help="对账单ID")
def st_get(id):
    """根据ID获取对账单详情"""
    backend = get_backend()
    result = backend.get("/api/statement/findById", params={"id": id})
    output(result)


@statement.command(name="export")
@click.option("--supplier-id", help="供应商ID")
@click.option("--customer-id", help="客户ID")
@click.option("--status", help="对账状态")
@click.option("--start-date", help="开始日期")
@click.option("--end-date", help="结束日期")
def st_export(supplier_id, customer_id, status, start_date, end_date):
    """导出对账单（Excel）"""
    backend = get_backend()
    params = {}
    if supplier_id:
        params["supplierId"] = supplier_id
    if customer_id:
        params["customerId"] = customer_id
    if status:
        params["status"] = status
    if start_date:
        params["startDate"] = start_date
    if end_date:
        params["endDate"] = end_date
    result = backend.get("/api/statement/export", params=params)
    output(result)


@statement.command(name="export-batch")
def st_export_batch():
    """批量导出对账单（Excel）"""
    backend = get_backend()
    result = backend.get("/api/statement/exportBatch")
    output(result)


@statement.command(name="comment")
def st_comment():
    """获取对账单备注"""
    backend = get_backend()
    result = backend.get("/api/statement/comment")
    output(result)
