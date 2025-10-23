# core/extract/extract_service.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

from core.search.file_discovery import discover_files
from core.search.file_discovery import DEFAULT_EXTS as SEARCH_DEFAULT_EXTS

INCLUDE_EXTS = {".json", ".log", ".txt"}  # we’ll try json first; txt/log may be JSON too


class ExtractionSummary:
    def __init__(self, scanned: int, parsed_ok: int, parsed_failed: int, written_path: str):
        self.scanned = scanned
        self.parsed_ok = parsed_ok
        self.parsed_failed = parsed_failed
        self.written_path = written_path


class ExtractService:
    """
    Schema-based extractor for JSON logs.
    - For each file, attempts to parse JSON (UTF-8, ignore errors).
    - Extracts selected fields given as dot-paths.
    - Missing fields -> None (null in JSON; empty in TXT).
    - Arrays: if the path walks into a list, we collect values from each element.
      e.g. chat_history.role -> ["user", "assistant"]
    """

    def __init__(self, include_exts: List[str] | None = None):
        self.include_exts = set(include_exts or list(INCLUDE_EXTS))

    # ---------- Public API ----------

    def extract_to_json(
        self,
        folder: str,
        selected_fields: List[str],
        out_path: str,
    ) -> ExtractionSummary:
        records, scanned, ok, failed = self._collect_records(folder, selected_fields)
        Path(out_path).write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
        return ExtractionSummary(scanned, ok, failed, out_path)

    def extract_to_txt(
        self,
        folder: str,
        selected_fields: List[str],
        out_path: str,
    ) -> ExtractionSummary:
        records, scanned, ok, failed = self._collect_records(folder, selected_fields)

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

    # ---------- Internals ----------

    def _collect_records(self, folder: str, selected_fields: List[str]) -> Tuple[List[Dict[str, Any]], int, int, int]:
        files = discover_files(folder, include_exts=self.include_exts)
        records: List[Dict[str, Any]] = []
        scanned = 0
        ok = 0
        failed = 0

        for fpath in files:
            scanned += 1
            try:
                text = Path(fpath).read_text(encoding="utf-8", errors="ignore").strip()
                # Try JSON parse (many .log/.txt are actually json lines or single json objects)
                data = json.loads(text)
            except Exception:
                failed += 1
                continue

            row: Dict[str, Any] = {"__file__": str(fpath)}
            for path in selected_fields:
                row[path] = self._get_dot_value(data, path)
            records.append(row)
            ok += 1

        return records, scanned, ok, failed

    def _get_dot_value(self, data: Any, dot: str) -> Any:
        """
        Traverse nested dict/list by dot-path.
        If we hit a list and the next key is for dict items, collect values from each element.
        Examples:
         - "timestamp" -> "..."
         - "pipeline.intent_identifier.intent" -> "ask_person_birthplace"
         - "chat_history.role" -> ["user","assistant"]
        """
        keys = dot.split(".")
        return self._walk(data, keys)

    def _walk(self, node: Any, keys: List[str]) -> Any:
        if not keys:
            return node

        head, *tail = keys

        if isinstance(node, dict):
            if head not in node:
                return None
            return self._walk(node[head], tail)

        if isinstance(node, list):
            # collect from each element
            collected: List[Any] = []
            for item in node:
                collected.append(self._walk(item, keys))
            # flatten single-level lists of None -> None if all None
            all_none = all(x is None for x in collected)
            if all_none:
                return None
            return collected

        # primitive encountered before path ends -> not found
        return None
