# core/schema/parsers/default_parser.py
from __future__ import annotations
from typing import Dict, Any, List

from .base_parser import BaseParser
from core.utils.dot_walker import get_dot_value

class DefaultParser(BaseParser):
    """
    Generic parser using dot-walker; always safe fallback.
    """

    def _fallback_get(self, data: Dict[str, Any], field: str):
        return get_dot_value(data, field)
