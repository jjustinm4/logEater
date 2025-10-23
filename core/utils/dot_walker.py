# core/util/dot_walker.py
from __future__ import annotations
from typing import Any, List

def get_dot_value(data: Any, dot_path: str) -> Any:
    """
    Traverse nested dict/list by dot-path.
    Arrays: collect values per element when walking lists.
    """
    keys = dot_path.split(".")
    return _walk(data, keys)

def _walk(node: Any, keys: List[str]) -> Any:
    if not keys:
        return node

    head, *tail = keys

    if isinstance(node, dict):
        if head not in node:
            return None
        return _walk(node[head], tail)

    if isinstance(node, list):
        collected = [_walk(item, keys) for item in node]
        if all(x is None for x in collected):
            return None
        return collected

    return None
