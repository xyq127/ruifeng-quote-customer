"""分类管理"""

import json
import click
from ..platform_service_cli import get_backend, output


@click.group()
def product_category():
    """分类管理"""
    pass


@product_category.command(name="list")
@click.option("--page", default=1, type=int, help="页码")
@click.option("--size", default=15, type=int, help="每页条数")
def pc_list(page, size):
    """获取分类列表"""
    backend = get_backend()
    result = backend.get("/api/productCategory/list", params={"page": page, "size": size})
    output(result)


@product_category.command(name="all")
def pc_all():
    """获取全部分类"""
    backend = get_backend()
    result = backend.get("/api/productCategory/all")
    output(result)


@product_category.command(name="tree")
def pc_tree():
    """获取分类树"""
    backend = get_backend()
    result = backend.get("/api/productCategory/tree")
    output(result)


@product_category.command(name="children")
@click.option("--parent", help="父级分类ID")
def pc_children(parent):
    """获取子分类"""
    backend = get_backend()
    params = {}
    if parent:
        params["parent"] = parent
    result = backend.get("/api/productCategory/childs", params=params)
    output(result)


@product_category.command(name="get")
@click.option("--id", required=True, help="分类ID")
def pc_get(id):
    """根据ID获取分类详情"""
    backend = get_backend()
    result = backend.get("/api/productCategory/findById", params={"id": id})
    output(result)


@product_category.command(name="create")
@click.option("--category", required=True, help="分类名称")
@click.option("--num", required=True, type=int, help="排序号")
@click.option("--parent", help="父级分类ID")
def pc_create(category, num, parent):
    """创建分类"""
    backend = get_backend()
    data = {
        "category": category,
        "num": num,
    }
    if parent:
        data["parent"] = parent
    result = backend.post("/api/productCategory/save", data=data)
    output(result)


@product_category.command(name="update")
@click.option("--id", required=True, help="分类ID")
@click.option("--category", help="分类名称")
@click.option("--parent", help="父级分类ID")
def pc_update(id, category, parent):
    """更新分类"""
    backend = get_backend()
    data = {"id": id}
    if category:
        data["category"] = category
    if parent:
        data["parent"] = parent
    result = backend.post("/api/productCategory/update", data=data)
    output(result)


@product_category.command(name="batch-update")
@click.option("--data-file", type=click.Path(exists=True), required=True, help="JSON 数据文件路径")
def pc_batch_update(data_file):
    """批量更新分类"""
    backend = get_backend()
    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    result = backend.post("/api/productCategory/updateBatch", data=data)
    output(result)


@product_category.command(name="comment")
def pc_comment():
    """获取分类备注"""
    backend = get_backend()
    result = backend.get("/api/productCategory/comment")
    output(result)
