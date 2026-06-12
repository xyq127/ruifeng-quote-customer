"""连接配置管理命令（支持测试/正式多环境）."""

import os
import click
from ..platform_service_cli import get_backend, get_session, output, _backend, _repl_skin
from ..utils.backend import PlatformServiceBackend


@click.group(name="config")
def config_cmd():
    """配置和管理连接参数（支持 test/prod 环境）"""
    pass


@config_cmd.command(name="use")
@click.argument("env", type=click.Choice(["test", "prod"]))
def config_use(env):
    """切换到指定环境 (test / prod)"""
    global _backend
    session = get_session()
    session.current_env = env

    server = session.get_env_server(env)
    if _repl_skin:
        _repl_skin.success(f"已切换到 {env} 环境 (服务器: {server})")

    # Re-init backend with the new env's config
    if session.base_url:
        try:
            _backend = PlatformServiceBackend(session.base_url, session.token)
            if _repl_skin:
                _repl_skin.info(f"已连接: {session.base_url}")
        except Exception as e:
            if _repl_skin:
                _repl_skin.warning(str(e))
    else:
        if _repl_skin:
            _repl_skin.warning(f"{env} 环境尚未配置 base-url，请用 config set 设置")
    output(session.to_dict())


@config_cmd.command(name="set")
@click.option("--env", "target_env", type=click.Choice(["test", "prod"]),
              help="目标环境（省略则使用当前环境）")
@click.option("--base-url", help="平台服务 Base URL")
@click.option("--token", help="Bearer Token")
def config_set(target_env, base_url, token):
    """设置连接参数（为指定环境或当前环境）"""
    global _backend
    session = get_session()

    env = target_env or session.current_env
    if not env:
        if _repl_skin:
            _repl_skin.error("请先用 config use <env> 选择环境，或用 --env 指定")
        return

    # If setting for a different env than current, switch first
    if target_env and target_env != session.current_env:
        session.current_env = target_env

    if base_url:
        session.base_url = base_url
    if token:
        session.token = token

    if session.base_url:
        _backend = PlatformServiceBackend(session.base_url, session.token)

    server = session.get_env_server(env)
    if _repl_skin:
        _repl_skin.success(f"[{env}] 环境配置已更新 (服务器: {server}, URL: {session.base_url})")
    output(session.to_dict())


@config_cmd.command(name="show")
def config_show():
    """显示所有环境配置状态"""
    session = get_session()
    if not _json_output_requested():
        _print_env_table(session)
    output(session.to_dict())


def _json_output_requested() -> bool:
    """Check if --json flag is active (access via parent context)."""
    import sys
    return "--json" in sys.argv


def _print_env_table(session):
    """Print a human-readable env overview."""
    envs = session.list_envs()
    if _repl_skin:
        _repl_skin.section("环境配置")
    for name, cfg in envs.items():
        marker = " *" if cfg["is_current"] else "  "
        status = "已配置" if cfg["base_url"] else "未配置"
        token_mark = " (有Token)" if cfg["has_token"] else ""
        line = f"{marker} [{name}] {cfg['server']} — {status}{token_mark}"
        if cfg["base_url"]:
            line += f" → {cfg['base_url']}"
        if cfg["is_current"]:
            click.secho(line, fg="green")
        else:
            click.echo(line)
    click.echo()


@config_cmd.command(name="test")
def config_test():
    """测试当前环境连接"""
    session = get_session()
    backend = get_backend()

    if _repl_skin:
        _repl_skin.info(f"测试环境 [{session.current_env}] → {session.base_url}")

    if backend.validate_connection():
        if _repl_skin:
            _repl_skin.success(f"[{session.current_env}] 连接测试成功")
        output({"status": "ok", "env": session.current_env, "base_url": backend.base_url})
    else:
        if _repl_skin:
            _repl_skin.error(f"[{session.current_env}] 连接测试失败")
        output({"status": "failed", "env": session.current_env, "base_url": backend.base_url})


@config_cmd.command(name="clear")
@click.option("--env", "target_env", type=click.Choice(["test", "prod"]),
              help="要清除的环境（省略则清除全部）")
def config_clear(target_env):
    """清除配置"""
    session = get_session()
    if target_env:
        session.clear(env=target_env)
        if _repl_skin:
            _repl_skin.success(f"[{target_env}] 环境配置已清除")
    else:
        session.clear()
        if _repl_skin:
            _repl_skin.success("所有配置已清除")
    output({"status": "cleared", "env": target_env or "all"})


@config_cmd.command(name="login")
@click.option("--mobile", required=True, prompt="手机号", help="登录手机号")
@click.option("--password", "--pwd", help="密码（不传则交互式输入，或设置 PLATFORM_PASSWORD 环境变量）")
@click.option("--timeout", default=30, type=int, help="请求超时秒数")
def config_login(mobile, password, timeout):
    """登录并保存 Token 到当前环境配置.

    通过手机号和密码获取平台访问令牌，自动保存到当前环境.
    登录成功后账号密码也会保存到配置文件（仅本用户可读），
    此后 token 过期时所有命令会自动重新登录，无需手动操作.
    密码可通过以下方式提供（优先级递减）:
    1. PLATFORM_PASSWORD 环境变量（适合脚本化场景）
    2. --password 选项
    3. 交互式输入
    """
    global _backend
    session = get_session()

    if not session.base_url:
        click.secho("错误: 请先配置 base-url（使用 config set --base-url）", fg='red', err=True)
        return

    pwd = password or os.environ.get("PLATFORM_PASSWORD")
    if not pwd:
        pwd = click.prompt("密码", hide_input=True)
    if not pwd.strip():
        click.secho("错误: 密码不能为空", fg='red', err=True)
        return

    mobile = mobile.strip()
    login_backend = PlatformServiceBackend(session.base_url)
    try:
        data = login_backend.login(mobile, pwd, timeout=timeout)
    except RuntimeError as e:
        click.secho(str(e), fg='red', err=True)
        return

    session.token = login_backend.token
    session.mobile = mobile
    session.password = pwd
    _backend = PlatformServiceBackend(
        session.base_url, login_backend.token,
        credentials={"mobile": mobile, "password": pwd})

    if _repl_skin:
        nick = data.get("nickName", "")
        _repl_skin.success(f"登录成功（{nick}）")
    else:
        click.echo("登录成功")

    output({"code": 200, "msg": "登录成功", "data": {"nickName": data.get("nickName", "")}})
