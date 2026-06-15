---
name: 工厂编号解析
description: 当用户需要解析雷迪克（Radick）工厂编号（DAC/DU/RAH 格式），提取内径、外径、高度、变型、ABS 齿数等物理参数，或生成 8 位核心编号用于后续 TecDoc/17vin 搜索时使用。数据清洗流程的起点。
version: 1.0.0
author: Hermes Agent
category: data-cleaning
---

# 雷迪克工厂编号解析

## 概述

将雷迪克工厂的产品编号拆解为物理参数，作为数据清洗的起点。这些参数用于在泰安联等第三方平台进行参数逆向匹配。

## 编号规则

工厂编号格式：`DAC{内径}{外径}{高度}{变型}-{后缀}(ABS{齿数})`

### 示例：`DAC39720037-2RZ(ABS88)`

| 位置 | 值 | 含义 |
|------|-----|------|
| 前缀 | DAC | 品牌/系列前缀 |
| 内径 | 39 | 内径 39mm |
| 外径 | 72 | 外径 72mm |
| 高度 | 00 | 高度（特殊编码，非直接 mm 值） |
| 变型 | 37 | 变型代号 |
| 后缀 | -2RZ | 密封形式（2RZ = 双面接触式密封） |
| ABS 齿数 | 88 | ABS 齿圈 88 齿 |

### 解析规则

```
DAC 39 72 00 37 -2RZ (ABS88)
    │  │  │  │    │      │
    │  │  │  │    │      └─ ABS齿数：括号内 ABS 后面的数字
    │  │  │  │    └─ 后缀：横杠后的密封/结构代码
    │  │  │  └─ 变型：高度后2位数字
    │  │  └─ 外径：第3-4位数字
    │  └─ 内径：第1-2位数字
    └─ 前缀：DAC 开头
```

## Python 解析脚本

```python
import re

def parse_factory_number(code: str) -> dict:
    """
    解析雷迪克工厂编号
    
    Args:
        code: 工厂编号，如 'DAC39720037-2RZ(ABS88)'
    
    Returns:
        dict: {
            'prefix': 'DAC',
            'inner_diameter': 39,
            'outer_diameter': 72,
            'height': '00',
            'variant': '37',
            'suffix': '-2RZ',
            'abs_teeth': 88,
            'core_number': '39720037',  # 内径+外径+高度+变型
            'full_match': True/False
        }
    """
    result = {
        'prefix': '',
        'inner_diameter': 0,
        'outer_diameter': 0,
        'height': '',
        'variant': '',
        'suffix': '',
        'abs_teeth': 0,
        'core_number': '',
        'full_match': False
    }
    
    # 标准化输入：去除空格，统一大小写
    code = code.strip().upper()
    
    # 正则匹配
    pattern = r'^([A-Z]+)(\d{2})(\d{2})(\d{2})(\d{2})(.*)$'
    match = re.match(pattern, code)
    
    if not match:
        return result
    
    result['prefix'] = match.group(1)
    result['inner_diameter'] = int(match.group(2))
    result['outer_diameter'] = int(match.group(3))
    result['height'] = match.group(4)
    result['variant'] = match.group(5)
    result['core_number'] = match.group(2) + match.group(3) + match.group(4) + match.group(5)
    
    # 提取后缀和ABS齿数
    remainder = match.group(6)
    
    # 提取 ABS 齿数
    abs_match = re.search(r'ABS(\d+)', remainder)
    if abs_match:
        result['abs_teeth'] = int(abs_match.group(1))
    
    # 提取后缀（横杠后的部分，不含ABS括号）
    suffix_match = re.match(r'(-[^(\s]*)', remainder)
    if suffix_match:
        result['suffix'] = suffix_match.group(1)
    
    result['full_match'] = True
    return result


def params_to_search_query(params: dict) -> str:
    """
    将解析后的参数转换为搜索关键词
    
    Args:
        params: parse_factory_number 的返回结果
    
    Returns:
        str: 搜索关键词，如 '39 72 00'
    """
    if not params['full_match']:
        return ''
    return f"{params['inner_diameter']} {params['outer_diameter']} {params['height']}"


if __name__ == '__main__':
    code = 'DAC39720037-2RZ(ABS88)'
    params = parse_factory_number(code)
    print(f"工厂编号: {code}")
    print(f"内径: {params['inner_diameter']}mm")
    print(f"外径: {params['outer_diameter']}mm")
    print(f"高度: {params['height']}")
    print(f"变型: {params['variant']}")
    print(f"后缀: {params['suffix']}")
    print(f"ABS齿数: {params['abs_teeth']}")
    print(f"搜索关键词: {params_to_search_query(params)}")
```

## 注意事项

1. **高度字段不是直接的 mm 值**，是工厂内部编码，需要在泰安联等平台按原样搜索
2. **变型代号**用于区分同一尺寸的不同产品版本
3. **ABS 齿数是可选字段**，不是所有产品都有
4. **前缀可能不只有 DAC**，不同产品线可能有不同前缀

## 使用场景

- 数据清洗：用内径/外径/高度在泰安联搜索，获取第三方 OE 进行交叉验证
- 参数逆向法：不依赖 OE 编号，只用物理参数匹配配件
- 产品入库校验：确认工厂编号与物理参数的一致性
