#!/usr/bin/env python3
"""Platform Service CLI — 睿峰智链汽车配件供应链平台 CLI 管理工具.

CLI harness for the platform-service (Spring Boot multi-module backend),
providing agent-friendly command-line access to all REST API endpoints.
"""

import click
import json
import os
import shlex
import sys
from typing import Any, Optional

from .utils.backend import PlatformServiceBackend
from .core.session import Session
from .utils.repl_skin import ReplSkin

_json_output = False
_backend: Optional[PlatformServiceBackend] = None
_session: Optional[Session] = None
_repl_skin: Optional[ReplSkin] = None


def get_backend() -> PlatformServiceBackend:
    if _backend is None:
        raise RuntimeError("Backend 未初始化，请先配置连接参数")
    return _backend


def get_session() -> Session:
    if _session is None:
        raise RuntimeError("Session 未初始化")
    return _session


def output(data: Any):
    """统一输出: --json 模式输出 JSON，否则人类可读格式。"""
    if _json_output:
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        if isinstance(data, dict):
            code = data.get('code', '')
            msg = data.get('msg', '')
            status = data.get('status', False)
            payload = data.get('data')

            if msg:
                color = 'green' if status else 'red'
                if _repl_skin:
                    if status:
                        _repl_skin.success(f"[{code}] {msg}")
                    else:
                        _repl_skin.error(f"[{code}] {msg}")
                else:
                    click.secho(f"[{code}] {msg}", fg=color)

            if payload is not None:
                if isinstance(payload, dict):
                    if 'content' in payload:
                        # Paginated
                        content = payload['content']
                        total = payload.get('totalElements', len(content))
                        click.secho(f"  共 {total} 条记录", fg='blue')
                        if isinstance(content, list):
                            for item in content:
                                _print_item(item)
                    else:
                        for k, v in payload.items():
                            if k != 'content':
                                click.echo(f"  {k}: {_format_value(v)}")
                        if 'content' in payload:
                            for item in payload['content']:
                                _print_item(item)
                elif isinstance(payload, list):
                    for item in payload:
                        if isinstance(item, dict):
                            _print_item(item)
                        else:
                            click.echo(f"  - {item}")
                else:
                    click.echo(f"  {payload}")
        elif isinstance(data, list):
            for item in data:
                click.echo(f"  - {item}")
        else:
            click.echo(f"  {data}")


def _print_item(item: dict):
    """打印单个对象的关键字段。"""
    name = item.get('name') or item.get('companyName') or item.get('nickName') or item.get('category') or item.get('id', '')
    id_val = item.get('id', '')
    status_val = item.get('status', '')
    extra = ''
    if 'mobile' in item:
        extra = f" | {item['mobile']}"
    if 'oe' in item:
        extra = f" | OE: {item['oe']}"
    if 'brand' in item:
        extra += f" | {item['brand']}"
    click.echo(f"  [{id_val}] {name} (status={status_val}){extra}")


def _format_value(v: Any) -> str:
    if isinstance(v, (list, dict)):
        return str(v)[:120]
    return str(v)


@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="JSON 输出模式")
@click.option("--env", "cli_env", type=click.Choice(["test", "prod"]),
              help="目标环境 (test / prod)")
@click.option("--base-url", help="平台服务 Base URL（覆盖 env 预设）")
@click.option("--token", help="Bearer Token（覆盖 env 预设）")
@click.pass_context
def cli(ctx, use_json, cli_env, base_url, token):
    """Platform Service CLI — 睿峰智链汽车配件供应链平台.

    连接后可通过命令行管理产品、客户/供应商、用户、库存、
    购物车、报价、采购单、出入库等所有业务模块.

    \b
    环境切换示例:
      cli-anything-platform-service --env test product list
      cli-anything-platform-service --env prod company customer list
    """
    global _json_output, _backend, _session, _repl_skin

    _json_output = use_json
    _session = Session()

    # Apply --env override (from CLI flag or env var)
    env = cli_env or os.environ.get("PLATFORM_ENV")
    if env:
        try:
            _session.current_env = env
        except ValueError:
            pass  # silently ignore invalid env from env var

    # CLI flags override saved config
    base_url = base_url or _session.base_url
    token = token or _session.token

    _repl_skin = ReplSkin("platform-service", version="1.0.0")

    if base_url:
        # 已保存账号密码时启用 401 自动重新登录，新 token 写回配置
        credentials = None
        if _session.mobile and _session.password:
            credentials = {"mobile": _session.mobile, "password": _session.password}

        def _persist_token(new_token):
            try:
                _session.token = new_token
            except Exception:
                pass

        try:
            _backend = PlatformServiceBackend(base_url, token, credentials=credentials,
                                              on_token_refresh=_persist_token)
            if not ctx.invoked_subcommand:
                _repl_skin.info(f"已连接 [{_session.current_env or 'default'}]: {base_url}")
        except Exception as e:
            _repl_skin.error(str(e))
            _backend = PlatformServiceBackend(base_url, token, credentials=credentials,
                                              on_token_refresh=_persist_token)
    else:
        _backend = None

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── Import command groups ─────────────────────────────────────────────

from .core.product import product
from .core.company import company
from .core.user import user
from .core.inventory import inventory
from .core.shopping_cart import shopping_cart
from .core.price import price, price_approval, price_list, price_item
from .core.quotation import quotation
from .core.purchase_order import purchase_order
from .core.stock_order import stock_order
from .core.menu import menu
from .core.role import role
from .core.warehouse import warehouse
from .core.product_category import product_category
from .core.payment_term import payment_term
from .core.statement import statement
from .core.config_cmd import config_cmd
from .core.data_clean import data_clean, register_commands

register_commands(data_clean)
cli.add_command(data_clean)
cli.add_command(product)
cli.add_command(company)
cli.add_command(user)
cli.add_command(inventory)
cli.add_command(shopping_cart)
cli.add_command(price)
cli.add_command(price_approval)
cli.add_command(price_list)
cli.add_command(price_item)
cli.add_command(quotation)
cli.add_command(purchase_order)
cli.add_command(stock_order)
cli.add_command(menu)
cli.add_command(role)
cli.add_command(warehouse)
cli.add_command(product_category)
cli.add_command(payment_term)
cli.add_command(statement)
cli.add_command(config_cmd)


# ── REPL ──────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def repl(ctx):
    """启动交互式 REPL 模式"""
    global _json_output

    if _repl_skin is None:
        click.echo("Error: REPL requires skin initialization", err=True)
        return

    _repl_skin.print_banner()

    if _session and _session.current_env:
        _repl_skin.info(f"当前环境: {_session.current_env} ({_session.get_env_server(_session.current_env)})")
    if _session and _session.configured and _backend:
        _repl_skin.info(f"Base URL: {_session.base_url}")
        if _session.token:
            _repl_skin.info("Token: ***已配置***")

    _repl_skin.info("输入 'help' 查看可用命令, 'exit' 退出")

    while True:
        try:
            user_input = _repl_skin.prompt("platform-service")

            if not user_input.strip():
                continue

            if user_input.lower() in ('exit', 'quit', 'q'):
                _repl_skin.print_goodbye()
                break

            if user_input.lower() == 'help':
                cmds = _build_help_dict()
                _repl_skin.help(cmds)
                continue

            try:
                parts = shlex.split(user_input)
            except ValueError as e:
                _repl_skin.error(f"解析错误: {e}")
                continue

            command_name = parts[0]
            args = parts[1:]

            if command_name in cli.commands:
                try:
                    cli.commands[command_name].main(
                        args=args,
                        prog_name=command_name,
                        standalone_mode=False,
                    )
                except click.ClickException as e:
                    _repl_skin.error(e.format_message())
                except click.Abort:
                    _repl_skin.error("命令已中止")
                except click.exceptions.Exit as e:
                    if e.exit_code:
                        _repl_skin.error(f"命令退出, 状态码: {e.exit_code}")
            else:
                _repl_skin.error(f"未知命令: {command_name}")
                _repl_skin.hint("输入 'help' 查看可用命令")

        except KeyboardInterrupt:
            _repl_skin.print_goodbye()
            break
        except Exception as e:
            _repl_skin.error(f"错误: {e}")


def _build_help_dict() -> dict:
    """构建 REPL help 的命令列表。"""
    return {
        "config": "配置连接参数 (use/set/show/test/clear, 支持 test/prod 环境)",
        "data-clean": "数据清洗工具 (parse, backend-search, epc-query, taianlian-search, cross-validate, excel-process)",
        "product": "产品管理 (list, get, create, update, delete, on-shelf, off-shelf, sync)",
        "company": "公司管理 (customer/supplier list, get, create, audit, lock, unlock)",
        "user": "用户管理 (list, get, create, update)",
        "inventory": "库存管理 (list, get, delete, sync)",
        "shopping-cart": "购物车管理 (list, add, update, delete, batch-delete, count)",
        "price": "价格解析管理 (parse, export-quotes)",
        "price-approval": "价格变更审批 (pending, find-by-id, approve, reject, batch-approve, import)",
        "price-list": "价格清单管理 (list, find-all, find-by-id, create, update, delete)",
        "price-item": "价格清单明细管理 (list, find-by-price-list, create, update, delete, import)",
        "quotation": "报价管理 (list, get, create, delete)",
        "purchase-order": "采购单管理 (supplier/customer list, get, create, cancel)",
        "stock-order": "出入库管理 (list, get, purchase-in, order-out, set-location, post, delete)",
        "menu": "菜单管理 (list, update)",
        "role": "角色管理 (list, get, all, create, update, delete)",
        "warehouse": "仓库管理 (list, get, create, update, delete)",
        "product-category": "分类管理 (list, tree, get, create, update, batch-update)",
        "payment-term": "付款条件管理 (list, get, all, create, update, delete)",
        "statement": "对账单管理 (supplier, customer, get, export, export-batch)",
    }


def main():
    """Entry point."""
    cli()


if __name__ == '__main__':
    main()
