from __future__ import annotations

import re
import sys
from collections.abc import Iterable


def normalize_process_name(name: str) -> str:
    """规范化单个进程名，自动补齐 Windows 下的 `.exe` 后缀。"""
    normalized = name.strip()
    if not normalized:
        return ''
    if sys.platform == 'win32' and not normalized.lower().endswith('.exe'):
        normalized = f'{normalized}.exe'
    return normalized


def normalize_process_names(value: str | Iterable[str] | None) -> list[str]:
    """规范化进程名列表。"""
    if value is None:
        return []

    raw_items: list[str] = []
    if isinstance(value, str):
        raw_items.extend(re.split(r'[\r\n]+', value))
    else:
        for item in value:
            if item is None:
                continue
            if isinstance(item, str):
                raw_items.extend(re.split(r'[\r\n]+', item))
            else:
                raw_items.append(str(item))

    result: list[str] = []
    seen: set[str] = set()
    for raw_name in raw_items:
        name = normalize_process_name(raw_name)
        if not name:
            continue
        dedupe_key = name.lower() if sys.platform == 'win32' else name
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        result.append(name)
    return result


def process_name_equals(left: str | None, right: str | None) -> bool:
    """判断两个进程名是否相等，Windows 下按不区分大小写处理。"""
    if left is None or right is None:
        return left == right
    if sys.platform == 'win32':
        return normalize_process_name(left).lower() == normalize_process_name(right).lower()
    return normalize_process_name(left) == normalize_process_name(right)


def format_process_names_for_text(process_names: Iterable[str] | None) -> str:
    """将进程名列表格式化为多行文本。"""
    return '\n'.join(normalize_process_names(process_names))
