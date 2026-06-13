"""第三方查询结果本地缓存.

为 oe-query 等耗时的第三方查询(泰安联/17vin)提供基于文件的本地缓存，
避免相同输入重复查询。缓存文件存放于 ~/.claude/cache/ruifeng-data-clean/
（临时数据目录，不属于项目内文件）。

文件布局: CACHE_DIR/<namespace>/<key>.json
每个缓存文件内容: {"value": <被缓存的数据>, "ts": <写入时的unix时间戳>}
"""

import hashlib
import json
import os
import time

CACHE_DIR = os.path.expanduser("~/.claude/cache/ruifeng-data-clean/third-party-query")

DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7天


def _cache_key(*parts) -> str:
    """根据任意数量的字符串参数生成缓存key（sha256前24位）."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _cache_path(namespace: str, *key_parts) -> str:
    key = _cache_key(*key_parts)
    return os.path.join(CACHE_DIR, namespace, f"{key}.json")


def get_cached(namespace: str, *key_parts, ttl: int = DEFAULT_TTL_SECONDS):
    """读取缓存. 命中且未过期返回 {"value": ..., "ts": ...}，否则返回 None."""
    path = _cache_path(namespace, *key_parts)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
    except (OSError, ValueError):
        return None

    ts = record.get("ts")
    if ts is None or time.time() - ts > ttl:
        return None
    return record


def set_cached(namespace: str, *key_parts, value):
    """写入缓存，记录 value 和当前时间戳."""
    path = _cache_path(namespace, *key_parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    record = {"value": value, "ts": time.time()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False)
