# core/llm/schema_extractor.py
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .ollama_client import OllamaClient, OllamaError

# --- logging setup (library-friendly: no handlers added) ---
logger = logging.getLogger(__name__)


@dataclass
class ExtractionDiagnostics:
    prompt_chars: int
    raw_output_chars: int
    attempts: int


class SchemaExtractionError(RuntimeError):
    """Raised when schema extraction fails after all attempts."""
    def __init__(self, message: str, raw_output: str, diagnostics: ExtractionDiagnostics):
        super().__init__(message)
        self.raw_output = raw_output
        self.diagnostics = diagnostics


P1_PROMPT_TEMPLATE = """You are a precise log structure extractor.

Your task: Given a single JSON log sample, output a MINIMAL JSON SKELETON that preserves the same keys and structure.

Output Rules (IMPORTANT):
- Output valid JSON ONLY.
- DO NOT output json-schema. DO NOT output: "$schema", "type", "properties", "required", "additionalProperties".
- For strings: use "".
- For numbers: use 0.
- For booleans: use false.
- For arrays of objects: output a single object inside the array with its keys and empty primitive values.
- For arrays of primitives: output an empty array [].
- NO explanations, NO markdown fences, NO comments, NO prose — JSON ONLY.

Sample log:
{sample}

Now output ONLY the JSON skeleton for this log.
"""


class SchemaExtractor:
    """
    Orchestrates prompt creation, LLM call (Ollama), cleanup, lenient parse, JSON-Schema autoconversion, and retry.
    Public API:
        extract_schema(sample_log_text) -> Dict[str, Any]
        save_schema(class_name, schema) -> Path
    """

    def __init__(self, model: str = "llama3:latest", base_url: str = "http://localhost:11434", timeout: int = 90):
        self.model = model
        self.client = OllamaClient(base_url=base_url, timeout=timeout)

    # -------------- public API --------------

    def extract_schema(self, sample_log_text: str) -> Dict[str, Any]:
        """
        Returns a dict skeleton schema or raises SchemaExtractionError (with raw output + diagnostics).
        """
        prompt = self._build_prompt(sample_log_text)
        logger.debug("Built schema prompt (%d chars)", len(prompt))

        attempts = 0
        last_raw = ""
        for attempt in (1, 2):
            attempts = attempt
            try:
                raw = self._call_llm(prompt)
                last_raw = raw
                logger.debug("LLM raw output (chars=%d) [attempt=%d]", len(raw), attempt)
                schema = self._parse_or_convert_to_skeleton(raw)
                logger.info("Schema extracted successfully on attempt %d", attempt)
                return schema
            except Exception as e:
                logger.warning("Schema parse/convert failed on attempt %d: %s", attempt, e)

        diag = ExtractionDiagnostics(
            prompt_chars=len(prompt),
            raw_output_chars=len(last_raw),
            attempts=attempts,
        )
        raise SchemaExtractionError(
            "Schema generation failed after two attempts.",
            raw_output=last_raw,
            diagnostics=diag,
        )

    @staticmethod
    def save_schema(class_name: str, schema: Dict[str, Any], project_root: Optional[Path] = None) -> Path:
        if not class_name or not class_name.strip():
            raise ValueError("Class name cannot be empty.")
        safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", class_name.strip())

        root = project_root or Path(__file__).resolve().parents[2]  # project root
        schemas_dir = root / "registry" / "schemas"
        schemas_dir.mkdir(parents=True, exist_ok=True)

        out_path = schemas_dir / f"{safe_name}.json"
        out_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Schema saved: %s", out_path)
        return out_path

    # -------------- internals --------------

    def _build_prompt(self, sample: str) -> str:
        sample = sample.strip()
        return P1_PROMPT_TEMPLATE.replace("{sample}", sample)

    def _call_llm(self, prompt: str) -> str:
        # encourage deterministic, concise output
        return self.client.generate(
            model=self.model,
            prompt=prompt,
            options={
                "temperature": 0.0,
                "top_p": 0.9,
                "num_ctx": 4096,
            },
            keep_alive="5m",
        )

    def _parse_or_convert_to_skeleton(self, raw: str) -> Dict[str, Any]:
        """
        Robust parse pipeline with JSON-Schema AutoFix.
          1) strip code fences and whitespace
          2) extract largest {...} block
          3) json.loads (+ minor repairs)
          4) if it looks like JSON-Schema, convert to skeleton
          5) ensure dict root and no JSON-Schema markers remain
        """
        cleaned = self._clean_output(raw)
        block = self._extract_json_block(cleaned)

        # First pass parse
        parsed = self._json_loads_lenient(block)

        # If the model returned a JSON array or primitive accidentally, reject.
        if not isinstance(parsed, dict):
            raise ValueError("Top-level JSON must be an object/dict.")

        # AutoFix JSON-Schema → Skeleton if needed
        if self._looks_like_json_schema(parsed):
            logger.debug("Detected JSON-Schema structure; converting to skeleton.")
            skeleton = self._jsonschema_to_skeleton(parsed)
            if not isinstance(skeleton, dict):
                raise ValueError("Converted skeleton is not an object.")
            # final sanity: ensure no JSON-Schema markers remain
            if self._looks_like_json_schema(skeleton):
                raise ValueError("Post-conversion still resembles JSON-Schema; aborting.")
            return skeleton

        # else: assume it's already a skeleton
        # sanity: ensure it doesn't contain obvious schema keywords
        if self._contains_schema_keywords(parsed):
            raise ValueError("Output still contains schema keywords; expected plain skeleton.")
        return parsed

    @staticmethod
    def _clean_output(text: str) -> str:
        # remove fenced code blocks like ```json ... ```
        text = text.strip()
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return text.strip()

    @staticmethod
    def _extract_json_block(text: str) -> str:
        """
        Find the largest {...} region; if not found, return original text.
        """
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
        return text

    @staticmethod
    def _minor_repairs(text: str) -> str:
        """
        Apply small, safe repairs:
          - Remove trailing commas before } or ]
          - Strip BOM if present
        """
        # Strip BOM
        if text.startswith("\ufeff"):
            text = text.lstrip("\ufeff")

        # Remove trailing commas before closing braces/brackets
        text = re.sub(r",(\s*[}\]])", r"\1", text)
        return text

    def _json_loads_lenient(self, text: str) -> Any:
        try:
            return json.loads(text)
        except Exception as e_first:
            logger.debug("First json.loads failed: %s", e_first)
            repaired = self._minor_repairs(text)
            return json.loads(repaired)  # may still raise; caller handles

    # -------- JSON-Schema detection & conversion --------

    @staticmethod
    def _looks_like_json_schema(obj: Any) -> bool:
        """Detect common JSON-Schema layout at the root."""
        if not isinstance(obj, dict):
            return False
        if "$schema" in obj:
            return True
        # the pair of "type": "object" and "properties": {...} is a strong signal
        if obj.get("type") == "object" and isinstance(obj.get("properties"), dict):
            return True
        # sometimes root has only "properties"
        if "properties" in obj and isinstance(obj["properties"], dict):
            return True
        return False

    @staticmethod
    def _contains_schema_keywords(obj: Any) -> bool:
        """Shallow check for leftover schema keywords in what should be a skeleton."""
        if not isinstance(obj, dict):
            return False
        keywords = {"$schema", "type", "properties", "required", "additionalProperties", "items"}
        return any(k in obj for k in keywords)

    def _jsonschema_to_skeleton(self, schema_obj: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a JSON-Schema object to our minimal skeleton.
        Handles:
          - type: object / array / string / number / integer / boolean
          - properties
          - items (array)
          - union types like ["string","null"] -> choose non-null base
        """
        def choose_type(t: Union[str, list, None]) -> Optional[str]:
            if isinstance(t, list):
                # choose first non-null
                for x in t:
                    if x != "null":
                        return x
                return "null"
            return t

        def convert(node: Any) -> Any:
            if not isinstance(node, dict):
                # If it's not a schema dict, best effort: return empty object
                return {}

            t = choose_type(node.get("type"))
            if t == "object" or ("properties" in node and isinstance(node["properties"], dict)):
                props = node.get("properties", {})
                out: Dict[str, Any] = {}
                for k, v in props.items():
                    out[k] = convert(v)
                return out
            elif t == "array":
                items = node.get("items")
                if isinstance(items, dict):
                    child = convert(items)
                    # If array of objects → include one object; if primitives → []
                    if isinstance(child, dict):
                        return [child]
                    else:
                        return []
                else:
                    # unknown items → treat as primitives
                    return []
            elif t == "string":
                return ""
            elif t == "number" or t == "integer":
                return 0
            elif t == "boolean":
                return False
            elif t is None:
                # If no 'type' but nested hints exist (rare), best effort:
                # Prefer properties/items if present.
                if "properties" in node:
                    return convert({"type": "object", "properties": node["properties"]})
                if "items" in node:
                    return convert({"type": "array", "items": node["items"]})
                return {}
            else:
                # fallback for unknown types
                return ""

        # Root conversion
        result = convert(schema_obj)
        # Ensure dict root (some schemas can be arrays at root; we disallow for our use-case)
        if not isinstance(result, dict):
            result = {}
        return result
