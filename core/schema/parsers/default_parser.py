# core/schema/parsers/default_parser.py
from __future__ import annotations
from typing import Dict, Any, List, Optional

from .base_parser import BaseParser
from core.utils.dot_walker import get_dot_value

class DefaultParser(BaseParser):
    """
    Generic, schema-aware parser:
      - Uses dot-walker to fetch values.
      - If a field is missing, returns a default INFERRED FROM THE SCHEMA SKELETON:
          * dict  -> {}
          * list  -> []
          * other -> ""   (strings, numbers, booleans, null)
    """

    def __init__(self) -> None:
        self._schema_skeleton: Optional[Dict[str, Any]] = None

    # Called by ExtractService before extraction (see updated service below)
    def set_schema(self, schema_skeleton: Dict[str, Any]) -> None:
        self._schema_skeleton = schema_skeleton

    def extract(self, data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for f in fields:
            # Allow overrides hook
            overridden = self.extract_field(data, f)
            if overridden is not None:
                result[f] = overridden
                continue

            val = get_dot_value(data, f)

            if val is None:
                # Missing in this log → return default based on schema node
                expected = self._schema_node_for_path(f)
                result[f] = self._default_for_schema_node(expected)
            else:
                result[f] = val
        return result

    def extract_field(self, data: Dict[str, Any], field: str):
        # No special overrides by default; subclasses can customize
        return None

    # -------- schema helpers --------

    def _schema_node_for_path(self, dot_path: str) -> Any:
        """
        Traverse schema skeleton using the dot path.
        When encountering a list, descend into its first element if it's a dict; otherwise treat as list node.
        """
        if not self._schema_skeleton:
            return None

        node: Any = self._schema_skeleton
        parts = dot_path.split(".")

        for key in parts:
            if isinstance(node, dict):
                if key in node:
                    node = node[key]
                else:
                    # Key missing in skeleton → unknown type, fallback to ""
                    return None
            elif isinstance(node, list):
                # For lists, we expect a single representative element
                if node and isinstance(node[0], dict):
                    # continue traversal in the representative object
                    node = node[0]
                    # retry same key on this dict level
                    if key in node:
                        node = node[key]
                    else:
                        return None
                else:
                    # primitive arrays or empty arrays
                    return node
            else:
                # primitive reached before path ends → unknown
                return None

        return node

    @staticmethod
    def _default_for_schema_node(node: Any) -> Any:
        if isinstance(node, dict):
            return {}
        if isinstance(node, list):
            return []
        # for primitives & unknowns, we use "" (consistent with skeleton rules)
        return ""

    def _fallback_get(self, data: Dict[str, Any], field: str):
        return get_dot_value(data, field)
