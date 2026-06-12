"""价格解析管理命令."""

import json

import click
from ..platform_service_cli import get_backend, output


@click.group()
def price():
    """价格解析管理"""
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
@click.option("--data-file", type=click.Path(exists=True), required=True, help="JSON 文件路径，内容为 [{inventoryId, c0dig0}]")
def price_export_quotes(data_file):
    """导出报价单"""
    backend = get_backend()
    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    result = backend.post("/api/price/export", json=data)
    output(result)
