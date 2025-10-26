# core/schema/parsers/factory.py
from __future__ import annotations
import importlib
import re
from typing import Type

from .base_parser import BaseParser
from .default_parser import DefaultParser

def _safe_module_name(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return f"{s}_parser"

def _class_name_from_schema(name: str) -> str:
    core = re.sub(r"[^a-zA-Z0-9]+", " ", name).title().replace(" ", "")
    return core + "Parser" if not core.endswith("Parser") else core

class ParserFactory:
    @staticmethod
    def get(schema_name: str) -> BaseParser:
        """
        Returns a schema-specific parser if generated, otherwise DefaultParser.
        """
        module_name = _safe_module_name(schema_name)
        class_name = _class_name_from_schema(schema_name)

        fqmn = f"core.schema.parsers.{module_name}"
        try:
            mod = importlib.import_module(fqmn)
            cls: Type[BaseParser] = getattr(mod, class_name)
            inst = cls()
            if not isinstance(inst, BaseParser):
                raise TypeError(f"{class_name} must inherit BaseParser")
            return inst
        except Exception:
            return DefaultParser()
