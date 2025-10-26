# core/schema/parsers/default_parser.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
from .base_parser import BaseParser
import re


class DefaultParser(BaseParser):
    """
    Robust Matching-Based Parser (tailored)
      - Case-insensitive
      - Underscore == space
      - Strips delimiter tails for matching only: "--", "—", "-", ":"
      - Strips trailing " of <digits>" for matching only
      - ExtractionMatch = FIRST
    """

    def extract(self, data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for field in fields:
            val = self._resolve_field(data, field)
            results[field] = val
        return results

    # ---------------- core resolution ----------------
    def _resolve_field(self, data: Any, field: str) -> Any:
        if not isinstance(data, dict):
            return ""

        # 1) direct match at this level
        raw_key = self._find_match_key(data, field)
        if raw_key:
            return data[raw_key]

        # 2) one-level wrapper (e.g., {"log": {...}})
        for k, v in data.items():
            if isinstance(v, dict):
                raw_key = self._find_match_key(v, field)
                if raw_key:
                    return v[raw_key]

        # 3) deep search anywhere
        found = self._deep_find_match(data, field)
        if found is not None:
            return found

        # 4) not found
        return ""

    # ---------------- matching logic -----------------
    _delim_split = re.compile(r"\s*(?:--|—|-\s|:)\s*")
    _of_suffix = re.compile(r"\s+of\s+\d+\s*$", re.IGNORECASE)

    def _normalize_for_match(self, s: str) -> str:
        # lower, underscores->spaces
        x = s.lower().replace("_", " ")
        # cut at first delimiter tail
        x = self._delim_split.split(x, maxsplit=1)[0]
        # strip trailing " of <digits>"
        x = self._of_suffix.sub("", x)
        # collapse spaces
        x = re.sub(r"\s+", " ", x).strip()
        return x

    def _find_match_key(self, obj: Dict[str, Any], schema_key: str) -> Optional[str]:
        sk = self._normalize_for_match(schema_key)
        for raw_key in obj.keys():
            rk = self._normalize_for_match(raw_key)
            if rk.startswith(sk):
                return raw_key  # return the real key so we don't alter data
        return None

    def _deep_find_match(self, node: Any, schema_key: str) -> Optional[Any]:
        if isinstance(node, dict):
            mk = self._find_match_key(node, schema_key)
            if mk:
                return node[mk]
            for v in node.values():
                res = self._deep_find_match(v, schema_key)
                if res is not None:
                    return res
        elif isinstance(node, list):
            for item in node:
                res = self._deep_find_match(item, schema_key)
                if res is not None:
                    return res
        return None
