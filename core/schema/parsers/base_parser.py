# core/schema/parsers/base_parser.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseParser(ABC):
    """
    Strategy interface for schema-specific parsers.
    Implementations may override `extract_field` for custom handling.
    """

    def extract(self, data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for f in fields:
            overridden = self.extract_field(data, f)
            if overridden is not None:
                result[f] = overridden
            else:
                # Fallback to generic logic in DefaultParser subclass
                result[f] = self._fallback_get(data, f)
        return result

    def extract_field(self, data: Dict[str, Any], field: str):
        """
        Optional override point for per-field customization.
        Return None to use the default fallback behavior.
        """
        return None

    # Implementations should provide this via mixin / subclass.
    def _fallback_get(self, data: Dict[str, Any], field: str):
        raise NotImplementedError("_fallback_get must be provided by concrete parser")
