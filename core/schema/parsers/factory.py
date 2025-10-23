# core/schema/parsers/factory.py
from __future__ import annotations
import importlib
import re
from typing import Type

from .base_parser import BaseParser
from .default_parser import DefaultParser

def _safe_module_name(name: str) -> str:
    # normalize schema/class name to module stem
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return f"{s}_parser"  # e.g., sample_log -> sample_log_parser

def _class_name_from_schema(name: str) -> str:
    # Turn "sample_log" -> "SampleLogParser"
    core = re.sub(r"[^a-zA-Z0-9]+", " ", name).title().replace(" ", "")
    if not core.endswith("Parser"):
        core += "Parser"
    return core

class ParserFactory:
    @staticmethod
    def get(schema_name: str) -> BaseParser:
        """
        Try to dynamically import a schema-specific parser module:
          core.schema.parsers.<safe>_parser
        and instantiate class <CamelCase>Parser
        Falls back to DefaultParser if not found.
        """
        mod_name = _safe_module_name(schema_name)
        class_name = _class_name_from_schema(schema_name)

        fqmn = f"core.schema.parsers.{mod_name}"
        try:
            mod = importlib.import_module(fqmn)
            cls: Type[BaseParser] = getattr(mod, class_name)
            inst = cls()
            if not isinstance(inst, BaseParser):
                raise TypeError(f"{class_name} is not a BaseParser")
            return inst
        except Exception:
            # fallback to default parser
            return DefaultParser()
