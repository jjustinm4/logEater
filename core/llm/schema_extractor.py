# core/llm/schema_extractor.py
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .ollama_client import OllamaClient, OllamaError
from core.utils.json_utils import build_skeleton_from_json

logger = logging.getLogger(__name__)


@dataclass
class ExtractionDiagnostics:
    prompt_chars: int
    raw_output_chars: int
    attempts: int


class SchemaExtractionError(RuntimeError):
    def __init__(self, message: str, raw_output: str, diagnostics: ExtractionDiagnostics):
        super().__init__(message)
        self.raw_output = raw_output
        self.diagnostics = diagnostics


# --- AI refinement prompt (keeps structure, may reorder or tidy spacing; must return valid JSON only) ---
AI_REWRITE_PROMPT = """You are refining a JSON SCHEMA SKELETON.

Input is a JSON skeleton that already preserves the FULL structure and normalized keys.
Your job:
- Return VALID JSON ONLY (no markdown, no comments, no code fences).
- KEEP the exact structural depth and keys.
- You MAY reorder keys and remove obvious duplicates if any appear after normalization.
- You MUST NOT remove any branch or collapse objects/arrays.
- All primitives must remain "" (empty string), objects as {{}} and arrays as [] or [{{...}}] for arrays of objects.

Here is the skeleton to refine:

{skeleton}

Return ONLY the refined JSON.
"""


class SchemaExtractor:
    """
    Hybrid schema builder:
      1) Deterministic rule-based walk (always succeeds)
      2) Optional AI refinement (cosmetic; structure-preserving). Falls back to deterministic result if AI fails.
    """
    def __init__(self, model: str = "llama3:latest", base_url: str = "http://localhost:11434", timeout: int = 90):
        self.model = model
        self.client = OllamaClient(base_url=base_url, timeout=timeout)

    # -------------- public API --------------

    def extract_schema(self, sample_log_text: str, use_ai_refine: bool = True) -> Dict[str, Any]:
        # Step 1: deterministic skeleton
        try:
            base = build_skeleton_from_json(sample_log_text)
        except Exception as e:
            raise RuntimeError(f"Failed to parse input as JSON: {e}") from e

        if not use_ai_refine:
            return base

        # Step 2: AI refinement (non-destructive). If anything goes wrong, return base.
        try:
            refined = self._refine_with_ai(base)
            # Validate JSON and that it's a dict at top-level
            if not isinstance(refined, dict):
                return base
            return refined
        except Exception as e:
            logger.warning("AI refinement failed, returning deterministic skeleton. Error: %s", e)
            return base

    @staticmethod
    def save_schema(class_name: str, schema: Dict[str, Any], project_root: Optional[Path] = None) -> Path:
        if not class_name or not class_name.strip():
            raise ValueError("Class name cannot be empty.")
        safe_name = "".join(ch if ch.isalnum() or ch in ("_", "-", ".") else "_" for ch in class_name.strip())

        root = project_root or Path(__file__).resolve().parents[2]
        schemas_dir = root / "registry" / "schemas"
        schemas_dir.mkdir(parents=True, exist_ok=True)

        out_path = schemas_dir / f"{safe_name}.json"
        out_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
        return out_path

    # -------------- AI helper --------------

    def _refine_with_ai(self, skeleton: Dict[str, Any]) -> Dict[str, Any]:
        payload = json.dumps(skeleton, ensure_ascii=False, indent=2)
        prompt = AI_REWRITE_PROMPT.format(skeleton=payload)

        raw = self.client.generate(
            model=self.model,
            prompt=prompt,
            options={"temperature": 0.0, "top_p": 0.9, "num_ctx": 8192},
            keep_alive="5m",
        )

        # attempt strict json parse; if it fails try small repair (strip fences)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            # naive fence removal; if model returns fenced blocks

        try:
            result = json.loads(cleaned)
        except Exception as e:
            # tiny repair: if response contains any prefix/suffix text, try locating first '{' to last '}' span
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                fragment = cleaned[start:end+1]
                result = json.loads(fragment)
            else:
                raise RuntimeError(f"AI returned non-JSON response: {raw[:200]}") from e

        return result
