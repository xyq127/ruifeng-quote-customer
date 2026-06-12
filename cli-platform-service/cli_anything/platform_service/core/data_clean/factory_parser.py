"""Factory number parser — 工厂编号解析.

解析 DAC/DU/GDU/RAH/RAW 格式的汽车轮毂轴承工厂编号,
提取内径、外径、变型、高度、ABS 齿数等参数.
"""

import re
import json
import click


# ── 解析规则 ──────────────────────────────────────────

# DAC/DU/GDU: {前缀}{内2}{外2}{变2}{高2}{后缀}
BEARING_PATTERN = re.compile(
    r'^(?P<prefix>DAC|DU|GDU)'
    r'(?P<inner>\d{2})'
    r'(?P<outer>\d{2})'
    r'(?P<variant>\d{2})'
    r'(?P<height>\d{2})'
    r'(?P<suffix>.*)$',
    re.IGNORECASE
)

# ABS 齿数: (ABS88), /ABS96, ABS88 等
ABS_PATTERN = re.compile(r'ABS\s*(\d+)', re.IGNORECASE)

# 双值斜杠变体 (内径或高度可能有双值)
SLASH_PATTERN = re.compile(r'(\d+)/(\d+)')


def parse_factory_number(code: str) -> dict:
    """解析工厂编号为结构化数据.

    Args:
        code: 完整工厂编号，如 "DAC39720037-2RZ(ABS88)"

    Returns:
        {
            "code": 原始编号,
            "prefix": "DAC",
            "type": "一代轴承",
            "inner_diameter": 39,
            "outer_diameter": 72,
            "variant": 0,
            "height": 37,
            "abs_teeth": 88,
            "has_abs": true,
            "core_8digit": "39720037",
            "is_parsable": true,     # 是否可拆解参数
            "suffix": "-2RZ",
            "notes": ""
        }
    """
    result = {
        "code": code,
        "prefix": "",
        "type": "未知",
        "inner_diameter": None,
        "outer_diameter": None,
        "variant": None,
        "height": None,
        "abs_teeth": None,
        "has_abs": False,
        "core_8digit": "",
        "is_parsable": False,
        "suffix": "",
        "notes": "",
    }

    code_clean = code.strip()

    # 提取 ABS 齿数
    abs_match = ABS_PATTERN.search(code_clean)
    if abs_match:
        result["abs_teeth"] = int(abs_match.group(1))
        result["has_abs"] = True

    # 尝试匹配一代轴承格式
    m = BEARING_PATTERN.match(code_clean)
    if m:
        prefix = m.group('prefix').upper()
        inner = int(m.group('inner'))
        outer = int(m.group('outer'))
        variant = int(m.group('variant'))
        height = int(m.group('height'))
        suffix_raw = m.group('suffix')

        result["prefix"] = prefix
        result["inner_diameter"] = inner
        result["outer_diameter"] = outer
        result["variant"] = variant
        result["height"] = height
        result["core_8digit"] = f"{inner:02d}{outer:02d}{variant:02d}{height:02d}"
        result["is_parsable"] = True
        result["suffix"] = suffix_raw
        result["type"] = "一代轴承"
        return result

    # 尝试匹配轮毂单元格式 (RAH/RAW)
    if re.match(r'^(RAH|RAW)\d', code_clean, re.IGNORECASE):
        prefix = code_clean[:3].upper()
        result["prefix"] = prefix
        result["type"] = "二代/三代轮毂单元" if prefix == "RAH" else "轮毂单元(RAW)"
        result["is_parsable"] = False
        result["notes"] = "轮毂单元无法从编号拆解参数，需通过后台 API 获取"
        return result

    result["notes"] = "无法识别的编号格式"
    return result


def core_8digit(code: str) -> str:
    """提取8位核心编号 (内径+外径+变型+高度)，用于泰安联搜索."""
    parsed = parse_factory_number(code)
    return parsed["core_8digit"]


def normalize_oe(oe: str) -> str:
    """归一化 OE 号: 去横杠、去空格、全大写."""
    return oe.replace("-", "").replace(" ", "").upper()


def is_dac_format(code: str) -> bool:
    """判断是否为 DAC/DU/GDU 轴承编号格式（而非真实 OE 号）."""
    return bool(re.match(r'^(DAC|DU|GDU)\d{8}', code.strip(), re.IGNORECASE))


# ── Click command ─────────────────────────────────────

@click.command(name="parse")
@click.argument("code")
@click.option("--json", "use_json", is_flag=True, help="JSON 输出")
def parse_cmd(code, use_json):
    """解析工厂编号.

    CODE: 完整工厂编号，如 DAC39720037-2RZ(ABS88)
    """
    result = parse_factory_number(code)

    if use_json:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        click.secho(f"编号: {result['code']}", fg='cyan', bold=True)
        click.echo(f"  类型: {result['type']}")

        if result['is_parsable']:
            click.echo(f"  内径: {result['inner_diameter']}mm")
            click.echo(f"  外径: {result['outer_diameter']}mm")
            click.echo(f"  变型: {result['variant']:02d}")
            click.echo(f"  高度: {result['height']:02d}")
            click.echo(f"  搜索编号(8位): {result['core_8digit']}")
            click.echo(f"  后缀: {result['suffix']}")
        else:
            click.secho(f"  ⚠ {result['notes']}", fg='yellow')

        if result['has_abs']:
            click.echo(f"  ABS: {result['abs_teeth']} 齿")
        else:
            click.echo(f"  ABS: 无")
