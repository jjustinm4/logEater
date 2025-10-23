# core/extract/extract_service.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core.search.file_discovery import discover_files
from core.schema.parsers.factory import ParserFactory

INCLUDE_EXTS = {".json", ".log", ".txt"}

class ExtractionSummary:
    def __init__(self, scanned: int, parsed_ok: int, parsed_failed: int, written_path: str):
        self.scanned = scanned
        self.parsed_ok = parsed_ok
        self.parsed_failed = parsed_failed
        self.written_path = written_path

class ExtractService:
    """
    Schema-based extractor: routes to schema-specific parser via Factory.
    """

    def __init__(self, include_exts: List[str] | None = None):
        self.include_exts = set(include_exts or list(INCLUDE_EXTS))

    def extract_to_json(self, folder: str, schema_name: str, selected_fields: List[str], out_path: str) -> ExtractionSummary:
        records, scanned, ok, failed = self._collect_records(folder, schema_name, selected_fields)
        Path(out_path).write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
        return ExtractionSummary(scanned, ok, failed, out_path)

    def extract_to_txt(self, folder: str, schema_name: str, selected_fields: List[str], out_path: str) -> ExtractionSummary:
        records, scanned, ok, failed = self._collect_records(folder, schema_name, selected_fields)

        lines: List[str] = []
        for rec in records:
            lines.append("-" * 30)
            lines.append(f"File: {rec.get('__file__','')}")
            for f in selected_fields:
                val = rec.get(f, None)
                if isinstance(val, (dict, list)):
                    try:
                        val_str = json.dumps(val, ensure_ascii=False)
                    except Exception:
                        val_str = str(val)
                elif val is None:
                    val_str = ""
                else:
                    val_str = str(val)
                lines.append(f"{f}: {val_str}")
        text = "\n".join(lines) + ("\n" if lines else "")
        Path(out_path).write_text(text, encoding="utf-8")

        return ExtractionSummary(scanned, ok, failed, out_path)

    # ---------- internals ----------

    def _collect_records(self, folder: str, schema_name: str, selected_fields: List[str]) -> Tuple[List[Dict[str, Any]], int, int, int]:
        files = discover_files(folder, include_exts=self.include_exts)
        parser = ParserFactory.get(schema_name)
        records: List[Dict[str, Any]] = []
        scanned = 0
        ok = 0
        failed = 0

        for fpath in files:
            scanned += 1
            try:
                text = Path(fpath).read_text(encoding="utf-8", errors="ignore").strip()
                data = json.loads(text)
            except Exception:
                failed += 1
                continue

            row: Dict[str, Any] = {"__file__": str(fpath)}
            extracted = parser.extract(data, selected_fields)
            row.update(extracted)
            records.append(row)
            ok += 1

        return records, scanned, ok, failed
