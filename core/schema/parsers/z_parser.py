# Auto-generated parser for schema: z
from __future__ import annotations
from typing import Dict, Any, List

from .base_parser import BaseParser
from core.utils.dot_walker import get_dot_value

class ZParser(BaseParser):
    """
    Auto-generated parser for schema: z

    You may override logic for specific fields here.
    """

    def extract_field(self, data: Dict[str, Any], field: str):
        # Return a custom value here to override a field
        return None

    def _fallback_get(self, data: Dict[str, Any], field: str):
        # Default fallback uses dot-walker
        return get_dot_value(data, field)
