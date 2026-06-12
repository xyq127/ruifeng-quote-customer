"""产品管理"""

import json

import click
from ..platform_service_cli import get_backend, output


@click.group()
def product():
    """产品管理"""
    pass


@product.command(name="list")
@click.option("--keyword", help="搜索关键词")
@click.option("--car", help="适用车型")
@click.option("--supplier-id", help="供应商ID")
@click.option("--status", help="状态")
@click.option("--category-id", help="分类ID")
@click.option("--category-ids", help="分类ID列表(逗号分隔)")
@click.option("--abc-categories", help="ABC分类(逗号分隔)")
@click.option("--page", default=1, type=int, help="页码")
@click.option("--size", default=15, type=int, help="每页条数")
def product_list(keyword, car, supplier_id, status, category_id, category_ids, abc_categories, page, size):
    """获取产品列表"""
    backend = get_backend()
    params = {"page": page, "size": size}
    if keyword:
        params["keyword"] = keyword
    if car:
        params["car"] = car
    if supplier_id:
        params["supplierId"] = supplier_id
    if status:
        params["status"] = status
    if category_id:
        params["categoryId"] = category_id
    if category_ids:
        params["categoryIds"] = category_ids
    if abc_categories:
        params["abcCategories"] = abc_categories
    result = backend.get("/api/product/list", params=params)
    output(result)


@product.command(name="get")
@click.option("--id", required=True, help="产品ID")
def product_get(id):
    """根据ID获取产品详情"""
    backend = get_backend()
    result = backend.get("/api/product/findById", params={"id": id})
    output(result)


@product.command(name="create")
@click.option("--supplier-id", required=True, help="供应商ID")
@click.option("--oe", required=True, help="OE号")
@click.option("--code", required=True, help="产品编码")
@click.option("--name", required=True, help="产品名称")
@click.option("--brand", required=True, help="品牌")
@click.option("--car", required=True, help="适用车型")
@click.option("--company-car-id", required=True, help="车系ID")
@click.option("--car-code", required=True, help="车型编码")
@click.option("--category-id", required=True, help="分类ID")
@click.option("--invoice-name", help="开票名称")
@click.option("--purchase-price", type=float, help="采购价")
@click.option("--sale-price", type=float, help="销售价")
@click.option("--sale-unit", type=int, help="销售单位")
@click.option("--suggest-price", type=float, help="建议零售价")
@click.option("--type", help="产品类型")
@click.option("--presale", help="是否预售(true/false)")
@click.option("--nature", help="产品性质")
@click.option("--self-support", help="是否自营(true/false)")
@click.option("--new-product", help="是否新品(true/false)")
@click.option("--weight", help="重量")
@click.option("--volume", help="体积")
@click.option("--rate-num", help="税收编码")
@click.option("--tax", help="税率")
@click.option("--post", help="邮费")
@click.option("--warranty", help="质保")
@click.option("--params-json", required=True, help="产品分类参数数组 JSON，对应后端 params 字段")
@click.option("--ext-data-json", help="扩展字段 JSON，对应后端 extDataJson 字段")
@click.option("--attachment-price", type=float, help="附件价格")
@click.option("--suggest-type", type=int, help="是否代表型号: 1是, 0否")
def product_create(supplier_id, oe, code, name, brand, car, company_car_id, car_code, category_id, invoice_name, purchase_price, sale_price, sale_unit, suggest_price, type, presale, nature, self_support, new_product, weight, volume, rate_num, tax, post, warranty, params_json, ext_data_json, attachment_price, suggest_type):
    """创建产品"""
    backend = get_backend()
    params = _parse_json_option(params_json, "--params-json")
    if not isinstance(params, list):
        raise click.BadParameter("--params-json 必须是 JSON 数组")
    data = {
        "supplierId": supplier_id,
        "oe": oe,
        "code": code,
        "name": name,
        "brand": brand,
        "car": car,
        "companyCarId": company_car_id,
        "carCode": car_code,
        "categoryId": category_id,
        "purchasePrice": purchase_price if purchase_price is not None else 0,
        "salePrice": sale_price if sale_price is not None else 0,
        "suggestPrice": suggest_price if suggest_price is not None else 0,
        "saleUnit": sale_unit if sale_unit is not None else 1,
        "presale": _parse_bool_option(presale, "--presale") if presale is not None else False,
        "selfSupport": _parse_bool_option(self_support, "--self-support") if self_support is not None else True,
        "newProduct": _parse_bool_option(new_product, "--new-product") if new_product is not None else True,
        "tax": tax if tax else "含税",
        "post": post if post else "包邮",
        "params": params,
    }
    if invoice_name:
        data["invoiceName"] = invoice_name
    if type:
        data["type"] = type
    if nature:
        data["nature"] = nature
    if weight:
        data["weight"] = weight
    if volume:
        data["volume"] = volume
    if rate_num:
        data["rateNum"] = rate_num
    if warranty:
        data["warranty"] = warranty
    if ext_data_json:
        _parse_json_option(ext_data_json, "--ext-data-json")
        data["extDataJson"] = ext_data_json
    if attachment_price is not None:
        data["attachmentPrice"] = attachment_price
    if suggest_type is not None:
        data["suggestType"] = suggest_type
    result = backend.post("/api/product/save", data=data)
    output(result)


def _parse_json_option(value, option_name):
    """Parse a JSON CLI option and show a clear Click error on invalid JSON."""
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise click.BadParameter(f"{option_name} 不是合法 JSON: {exc.msg}") from exc


def _parse_bool_option(value, option_name):
    """Convert CLI boolean text to a real bool for backend DTO binding."""
    normalized = str(value).strip().lower()
    if normalized in ("true", "1", "yes", "y", "是"):
        return True
    if normalized in ("false", "0", "no", "n", "否"):
        return False
    raise click.BadParameter(f"{option_name} 只支持 true/false、1/0、yes/no、是/否")


@product.command(name="comment")
def product_comment():
    """获取产品字段说明"""
    backend = get_backend()
    result = backend.get("/api/product/comment")
    output(result)


@product.command(name="update")
@click.option("--id", required=True, help="产品ID")
@click.option("--supplier-id", help="供应商ID")
@click.option("--oe", help="OE号")
@click.option("--code", help="产品编码")
@click.option("--name", help="产品名称")
@click.option("--brand", help="品牌")
@click.option("--car", help="适用车型")
@click.option("--car-code", help="车型编码")
@click.option("--company-car-id", help="车系ID")
@click.option("--category-id", help="分类ID")
@click.option("--invoice-name", help="开票名称")
@click.option("--purchase-price", type=float, help="采购价")
@click.option("--sale-price", type=float, help="销售价")
@click.option("--sale-unit", type=int, help="销售单位")
@click.option("--suggest-price", type=float, help="建议零售价")
@click.option("--oem-price", type=float, help="OEM价格")
@click.option("--type", help="产品类型")
@click.option("--presale", help="是否预售(true/false)")
@click.option("--nature", help="产品性质")
@click.option("--self-support", help="是否自营(true/false)")
@click.option("--new-product", help="是否新品(true/false)")
@click.option("--weight", help="重量")
@click.option("--volume", help="体积")
@click.option("--rate-num", help="税收编码")
@click.option("--tax", help="税率")
@click.option("--post", help="邮费")
@click.option("--warranty", help="质保")
@click.option("--params-json", help="产品分类参数数组 JSON，对应后端 params 字段")
@click.option("--ext-data-json", help="扩展字段 JSON，对应后端 extDataJson 字段")
@click.option("--main-vehicle-model", help="标签车型")
@click.option("--reference-vehicle-model", help="通用车型")
@click.option("--abc-category", help="ABC分类")
@click.option("--attachment-price", type=float, help="附件价格")
@click.option("--suggest-type", type=int, help="是否代表型号: 1是, 0否")
def product_update(id, supplier_id, oe, code, name, brand, car, car_code, company_car_id, category_id, invoice_name, purchase_price, sale_price, sale_unit, suggest_price, oem_price, type, presale, nature, self_support, new_product, weight, volume, rate_num, tax, post, warranty, params_json, ext_data_json, main_vehicle_model, reference_vehicle_model, abc_category, attachment_price, suggest_type):
    """更新产品

    注意：后端 update 接口要求 params 非空，且语义接近完整表单更新，
    不建议只传 id + 少量字段直接更新真实产品。
    """
    backend = get_backend()
    data = {"id": id}
    if supplier_id:
        data["supplierId"] = supplier_id
    if oe:
        data["oe"] = oe
    if code:
        data["code"] = code
    if name:
        data["name"] = name
    if brand:
        data["brand"] = brand
    if car:
        data["car"] = car
    if car_code:
        data["carCode"] = car_code
    if company_car_id:
        data["companyCarId"] = company_car_id
    if category_id:
        data["categoryId"] = category_id
    if invoice_name:
        data["invoiceName"] = invoice_name
    if purchase_price is not None:
        data["purchasePrice"] = purchase_price
    if sale_price is not None:
        data["salePrice"] = sale_price
    if sale_unit is not None:
        data["saleUnit"] = sale_unit
    if suggest_price is not None:
        data["suggestPrice"] = suggest_price
    if oem_price is not None:
        data["oemPrice"] = oem_price
    if type:
        data["type"] = type
    if presale is not None:
        data["presale"] = _parse_bool_option(presale, "--presale")
    if nature:
        data["nature"] = nature
    if self_support is not None:
        data["selfSupport"] = _parse_bool_option(self_support, "--self-support")
    if new_product is not None:
        data["newProduct"] = _parse_bool_option(new_product, "--new-product")
    if weight:
        data["weight"] = weight
    if volume:
        data["volume"] = volume
    if rate_num:
        data["rateNum"] = rate_num
    if tax:
        data["tax"] = tax
    if post:
        data["post"] = post
    if warranty:
        data["warranty"] = warranty
    if params_json:
        params = _parse_json_option(params_json, "--params-json")
        if not isinstance(params, list):
            raise click.BadParameter("--params-json 必须是 JSON 数组")
        data["params"] = params
    if ext_data_json:
        # 后端字段是字符串，由后端 parseAndValidateExtData 解析。
        _parse_json_option(ext_data_json, "--ext-data-json")
        data["extDataJson"] = ext_data_json
    if main_vehicle_model:
        data["mainVehicleModel"] = main_vehicle_model
    if reference_vehicle_model:
        data["referenceVehicleModel"] = reference_vehicle_model
    if abc_category:
        data["abcCategory"] = abc_category
    if attachment_price is not None:
        data["attachmentPrice"] = attachment_price
    if suggest_type is not None:
        data["suggestType"] = suggest_type
    result = backend.post("/api/product/update", data=data)
    output(result)


@product.command(name="delete")
@click.option("--id", required=True, help="产品ID")
def product_delete(id):
    """删除产品"""
    backend = get_backend()
    result = backend.post("/api/product/delete", params={"id": id})
    output(result)


@product.command(name="on-shelf")
@click.option("--id", required=True, help="产品ID")
def product_on_shelf(id):
    """上架产品"""
    backend = get_backend()
    result = backend.post("/api/product/onShelf", params={"id": id})
    output(result)


@product.command(name="off-shelf")
@click.option("--id", required=True, help="产品ID")
def product_off_shelf(id):
    """下架产品"""
    backend = get_backend()
    result = backend.post("/api/product/offShelf", params={"id": id})
    output(result)


@product.command(name="sync")
def product_sync():
    """同步产品"""
    backend = get_backend()
    result = backend.post("/api/product/snyc")
    output(result)


@product.command(name="export")
@click.option("--keyword", help="搜索关键词")
@click.option("--supplier-id", help="供应商ID")
@click.option("--car", help="适用车型")
@click.option("--presale", help="是否预售")
@click.option("--self-support", help="是否自营")
@click.option("--new-product", help="是否新品")
@click.option("--abc-categories", help="ABC分类(逗号分隔)")
@click.option("--status", help="状态")
@click.option("--tax", help="税率")
@click.option("--post", help="邮费")
def product_export(keyword, supplier_id, car, presale, self_support, new_product, abc_categories, status, tax, post):
    """导出产品"""
    backend = get_backend()
    params = {}
    if keyword:
        params["keyword"] = keyword
    if supplier_id:
        params["supplierId"] = supplier_id
    if car:
        params["car"] = car
    if presale:
        params["presale"] = presale
    if self_support:
        params["selfSupport"] = self_support
    if new_product:
        params["newProduct"] = new_product
    if abc_categories:
        params["abcCategories"] = abc_categories
    if status:
        params["status"] = status
    if tax:
        params["tax"] = tax
    if post:
        params["post"] = post
    result = backend.get("/api/product/export", params=params)
    output(result)
