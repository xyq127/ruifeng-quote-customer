"""Data cleaning command group — 睿锋数据清洗 CLI 扩展.

数据清洗流程: 工厂编号解析 → 多源查询(泰安联/17vin/后台)
→ 交叉验证 → 输出报告.
"""

import click


@click.group()
def data_clean():
    """数据清洗工具集.

    工厂编号解析、泰安联/TecDoc 搜索、17vin EPC 查询、
    OE 交叉验证、Excel 处理等数据清洗操作.
"""
    pass


# ── 命令注册（由 platform_service_cli 调用）────────────

def register_commands(group):
    """将子命令注册到 data_clean 命令组（惰性导入避免循环依赖）."""
    from .factory_parser import parse_cmd
    from .backend_api import backend_search, backend_detail, num_save, num_batch_save, param_save
    from .epc import epc_query
    from .browser_search import taianlian_search
    from .cross_validate import cross_validate
    from .excel_processor import excel_process
    from .oe_query import oe_query
    from .quote_match import quote

    group.add_command(parse_cmd)
    group.add_command(backend_search)
    group.add_command(backend_detail)
    group.add_command(num_save)
    group.add_command(num_batch_save)
    group.add_command(param_save)
    group.add_command(epc_query)
    group.add_command(taianlian_search)
    group.add_command(cross_validate)
    group.add_command(excel_process)
    group.add_command(oe_query)
    group.add_command(quote)
