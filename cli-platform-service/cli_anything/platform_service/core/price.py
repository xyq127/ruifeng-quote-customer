"""价格管理（含价格审批、价格清单、价格清单明细）。"""

import json
import os

import click
from ..platform_service_cli import get_backend, output


# ── 原有 price 命令组 ──────────────────────────────────────────

@click.group()
def price():
    """价格管理（解析、报价导出）"""
    pass


@price.command(name="parse")
@click.option("--file", type=click.Path(exists=True), required=True, help="价格文件路径")
def price_parse(file):
    """解析价格文件"""
    backend = get_backend()
    files = {"file": open(file, "rb")}
    result = backend.post("/api/price/parse", files=files)
    output(result)


@price.command(name="export-quotes")
@click.option("--data-file", type=click.Path(exists=True), required=True,
              help="JSON 文件路径，内容为 [{inventoryId, c0dig0}]")
def price_export_quotes(data_file):
    """导出报价单"""
    backend = get_backend()
    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    result = backend.post("/api/price/export", json=data)
    output(result)


# ── price-approval 命令组（价格变更审批）──────────────────────

@click.group(name="price-approval")
def price_approval():
    """价格变更审批（列表/通过/拒绝/批量/导入）"""
    pass


@price_approval.command(name="pending")
@click.option("--status", type=int, help="状态：0-待审批, 1-已通过, 2-已拒绝")
@click.option("--entity-type", help="实体类型：PRODUCT / PRICE_LIST_ITEM")
@click.option("--batch-no", help="导入批次号（按批次查看明细时传入）")
@click.option("--code", help="产品编码模糊搜索")
@click.option("--page", default=1, type=int, help="页码")
@click.option("--size", default=15, type=int, help="每页条数")
def price_approval_pending(status, entity_type, batch_no, code, page, size):
    """审批列表（分页查询审批记录）"""
    backend = get_backend()
    params = {"page": page, "size": size}
    if status is not None:
        params["status"] = status
    if entity_type:
        params["entityType"] = entity_type
    if batch_no:
        params["batchNo"] = batch_no
    if code:
        params["code"] = code
    result = backend.get("/api/priceChangeApproval/pending", params=params)
    output(result)


@price_approval.command(name="find-by-id")
@click.option("--id", required=True, help="审批记录ID")
def price_approval_find_by_id(id):
    """根据ID查询审批记录"""
    backend = get_backend()
    result = backend.get("/api/priceChangeApproval/findById", params={"id": id})
    output(result)


@price_approval.command(name="approve")
@click.option("--id", required=True, help="审批记录ID")
@click.option("--remark", default="", help="审批备注")
def price_approval_approve(id, remark):
    """审批通过"""
    backend = get_backend()
    result = backend.post("/api/priceChangeApproval/approve", params={"id": id, "remark": remark})
    output(result)


@price_approval.command(name="reject")
@click.option("--id", required=True, help="审批记录ID")
@click.option("--remark", default="", help="审批备注")
def price_approval_reject(id, remark):
    """审批拒绝"""
    backend = get_backend()
    result = backend.post("/api/priceChangeApproval/reject", params={"id": id, "remark": remark})
    output(result)


@price_approval.command(name="batch-summary")
@click.option("--only-pending", default="true", help="是否只看有待审记录的批次（true/false）")
@click.option("--page", default=1, type=int, help="页码")
@click.option("--size", default=15, type=int, help="每页条数")
def price_approval_batch_summary(only_pending, page, size):
    """批次审批汇总（按导入批次聚合）"""
    backend = get_backend()
    params = {"onlyPending": only_pending, "page": page, "size": size}
    result = backend.get("/api/priceChangeApproval/batchSummary", params=params)
    output(result)


@price_approval.command(name="approve-batch")
@click.option("--batch-no", required=True, help="导入批次号")
@click.option("--remark", default="", help="审批备注")
def price_approval_approve_batch(batch_no, remark):
    """按批次整体通过"""
    backend = get_backend()
    result = backend.post("/api/priceChangeApproval/approveBatch",
                          params={"batchNo": batch_no, "remark": remark})
    output(result)


@price_approval.command(name="reject-batch")
@click.option("--batch-no", required=True, help="导入批次号")
@click.option("--remark", default="", help="审批备注")
def price_approval_reject_batch(batch_no, remark):
    """按批次整体拒绝"""
    backend = get_backend()
    result = backend.post("/api/priceChangeApproval/rejectBatch",
                          params={"batchNo": batch_no, "remark": remark})
    output(result)


@price_approval.command(name="approve-by-ids")
@click.option("--ids-json", required=True, help="审批记录ID列表 JSON，如 [\"id1\",\"id2\"]")
@click.option("--remark", default="", help="审批备注")
def price_approval_approve_by_ids(ids_json, remark):
    """批量通过（勾选多条）"""
    backend = get_backend()
    ids = json.loads(ids_json)
    result = backend.post("/api/priceChangeApproval/approveByIds",
                          data=ids, params={"remark": remark})
    output(result)


@price_approval.command(name="reject-by-ids")
@click.option("--ids-json", required=True, help="审批记录ID列表 JSON，如 [\"id1\",\"id2\"]")
@click.option("--remark", default="", help="审批备注")
def price_approval_reject_by_ids(ids_json, remark):
    """批量拒绝（勾选多条）"""
    backend = get_backend()
    ids = json.loads(ids_json)
    result = backend.post("/api/priceChangeApproval/rejectByIds",
                          data=ids, params={"remark": remark})
    output(result)


@price_approval.command(name="import")
@click.option("--file", type=click.Path(exists=True), required=True, help="Excel文件")
@click.option("--price-type", type=int, required=True,
              help="价格类型编码：2-P2、3-P3、6-采购价格、10-oem价格")
def price_approval_import(file, price_type):
    """Excel导入价格变更"""
    backend = get_backend()
    files = {"file": open(file, "rb")}
    result = backend.post("/api/priceChangeApproval/import",
                          data={"priceType": price_type}, files=files)
    output(result)


@price_approval.command(name="import-multi-price")
@click.option("--file", type=click.Path(exists=True), required=True, help="Excel文件")
def price_approval_import_multi_price(file):
    """Excel批量导入多种价格变更（采购价/OEM价/经销商价）"""
    backend = get_backend()
    files = {"file": open(file, "rb")}
    result = backend.post("/api/priceChangeApproval/importMultiPrice", files=files)
    output(result)


# ── price-list 命令组（价格清单）───────────────────────────────

@click.group(name="price-list")
def price_list():
    """价格清单管理（CRUD）"""
    pass


@price_list.command(name="list")
@click.option("--name", help="价格清单名称")
@click.option("--type", "price_type", help="价格类型：P1,P2,P3")
@click.option("--status", type=int, help="状态：0禁用，1启用")
@click.option("--page", default=1, type=int, help="页码")
@click.option("--size", default=15, type=int, help="每页条数")
def price_list_list(name, price_type, status, page, size):
    """价格清单列表"""
    backend = get_backend()
    params = {"page": page, "size": size}
    if name:
        params["name"] = name
    if price_type:
        params["type"] = price_type
    if status is not None:
        params["status"] = status
    result = backend.get("/api/priceList/list", params=params)
    output(result)


@price_list.command(name="find-all")
def price_list_find_all():
    """查询全部启用的价格清单（用于下拉选择）"""
    backend = get_backend()
    result = backend.get("/api/priceList/findAll")
    output(result)


@price_list.command(name="find-by-id")
@click.option("--id", required=True, help="价格清单ID")
def price_list_find_by_id(id):
    """根据ID查询价格清单"""
    backend = get_backend()
    result = backend.get("/api/priceList/findById", params={"id": id})
    output(result)


@price_list.command(name="create")
@click.option("--name", required=True, help="价格清单名称")
@click.option("--description", default="", help="描述")
@click.option("--status", type=int, default=0, help="状态：0禁用，1启用")
@click.option("--type", "price_type", default="", help="价格类型：P1,P2,P3")
def price_list_create(name, description, status, price_type):
    """新增价格清单"""
    backend = get_backend()
    params = {"name": name, "description": description,
              "status": status, "type": price_type}
    result = backend.post("/api/priceList/save", params=params)
    output(result)


@price_list.command(name="update")
@click.option("--id", required=True, help="价格清单ID")
@click.option("--name", help="价格清单名称")
@click.option("--description", help="描述")
@click.option("--status", type=int, help="状态：0禁用，1启用")
@click.option("--type", "price_type", help="价格类型：P1,P2,P3")
def price_list_update(id, name, description, status, price_type):
    """更新价格清单"""
    backend = get_backend()
    params = {"id": id}
    if name:
        params["name"] = name
    if description:
        params["description"] = description
    if status is not None:
        params["status"] = status
    if price_type:
        params["type"] = price_type
    result = backend.post("/api/priceList/update", params=params)
    output(result)


@price_list.command(name="delete")
@click.option("--id", required=True, help="价格清单ID")
def price_list_delete(id):
    """删除价格清单"""
    backend = get_backend()
    result = backend.post("/api/priceList/delete", params={"id": id})
    output(result)


# ── price-item 命令组（价格清单明细）───────────────────────────

@click.group(name="price-item")
def price_item():
    """价格清单明细管理（CRUD、导入）"""
    pass


@price_item.command(name="list")
@click.option("--price-list-id", required=True, help="价格清单ID")
@click.option("--keyword", help="关键字搜索")
@click.option("--page", default=1, type=int, help="页码")
@click.option("--size", default=15, type=int, help="每页条数")
def price_item_list(price_list_id, keyword, page, size):
    """价格清单明细列表"""
    backend = get_backend()
    params = {"priceListId": price_list_id, "page": page, "size": size}
    if keyword:
        params["keyword"] = keyword
    result = backend.get("/api/priceListItem/list", params=params)
    output(result)


@price_item.command(name="find-by-price-list")
@click.option("--price-list-id", required=True, help="价格清单ID")
def price_item_find_by_price_list(price_list_id):
    """根据价格清单ID查询所有明细"""
    backend = get_backend()
    result = backend.get("/api/priceListItem/findByPriceListId",
                         params={"priceListId": price_list_id})
    output(result)


@price_item.command(name="find-by-id")
@click.option("--id", required=True, help="明细ID")
def price_item_find_by_id(id):
    """根据ID查询价格清单明细"""
    backend = get_backend()
    result = backend.get("/api/priceListItem/findById", params={"id": id})
    output(result)


@price_item.command(name="create")
@click.option("--price-list-id", required=True, help="价格清单ID")
@click.option("--product-id", required=True, help="产品ID")
@click.option("--price", type=float, required=True, help="价格")
@click.option("--new-product-discount", type=float, help="新品折扣")
@click.option("--quantity-discounts-json", help="数量折扣 JSON，如 [{\"minQuantity\":10,\"price\":90}]")
def price_item_create(price_list_id, product_id, price, new_product_discount, quantity_discounts_json):
    """新增价格清单明细"""
    backend = get_backend()
    params = {"priceListId": price_list_id, "productId": product_id, "price": price}
    if new_product_discount is not None:
        params["newProductDiscount"] = new_product_discount
    if quantity_discounts_json:
        params["quantityDiscounts"] = quantity_discounts_json
    result = backend.post("/api/priceListItem/save", params=params)
    output(result)


@price_item.command(name="update")
@click.option("--id", required=True, help="明细ID")
@click.option("--price", type=float, help="价格（修改后自动提交价格审批）")
@click.option("--new-product-discount", type=float, help="新品折扣")
@click.option("--quantity-discounts-json", help="数量折扣 JSON")
def price_item_update(id, price, new_product_discount, quantity_discounts_json):
    """更新价格清单明细（价格修改自动提交审批）"""
    backend = get_backend()
    params = {"id": id}
    if price is not None:
        params["price"] = price
    if new_product_discount is not None:
        params["newProductDiscount"] = new_product_discount
    if quantity_discounts_json:
        params["quantityDiscounts"] = quantity_discounts_json
    result = backend.post("/api/priceListItem/update", params=params)
    output(result)


@price_item.command(name="delete")
@click.option("--id", required=True, help="明细ID")
def price_item_delete(id):
    """删除价格清单明细"""
    backend = get_backend()
    result = backend.post("/api/priceListItem/delete", params={"id": id})
    output(result)


@price_item.command(name="import")
@click.option("--price-list-id", required=True, help="价格清单ID")
@click.option("--file", type=click.Path(exists=True), required=True, help="Excel文件（产品ID、价格）")
def price_item_import(price_list_id, file):
    """导入价格清单明细"""
    backend = get_backend()
    files = {"file": open(file, "rb")}
    result = backend.post("/api/priceListItem/import",
                          data={"priceListId": price_list_id}, files=files)
    output(result)
