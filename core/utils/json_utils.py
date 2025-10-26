# core/utils/json_utils.py
from __future__ import annotations

import json
import re
from typing import Any, Dict, List


# ----------------------------
# Key normalization (rule-based)
# ----------------------------
# Goal: keep the base human-readable part, strip dynamic/descriptive suffixes.
# Examples:
#   "chat history--スマートフォンとタブ" -> "chat history"
#   "final_prompt - 日本語"             -> "final_prompt"
#   "response_of_1"                    -> "response"
#   "subquery_3_details"               -> "subquery"
#   "request: user clicked button"     -> "request"
#
# We DO NOT rewrite words, just strip suffix noise/digits after a delimiter or pattern.

_DELIM_PATTERN = re.compile(r"""
    \s*                # optional whitespace
    (?:--|—|:-|:-\s|-\s|:| - ) # common delimiters (greedy-ish; handled by regex engine)
    .*$                # everything after the first delimiter
""", re.VERBOSE)

_INDEX_SUFFIX = re.compile(r"""
    (                  # capture base
      [A-Za-z][A-Za-z0-9 ]*
    )
    (?:                # non-capturing: suffixes to strip
      (?:_of_\d+)|     # _of_12
      (?:_\d+)|        # _12
      (?:-\d+)|        # -12
      (?:\s+\d+)       # space 12
    )
    .*$
""", re.VERBOSE)

def normalize_key(key: str) -> str:
    k = (key or "").strip()

    # 1) cut at first delimiter tail: --, —, " - ", ":", "-", ": "
    #    everything after the delimiter is considered descriptive noise
    k = re.split(r"\s*(?:--|—|-\s|:)\s*", k, maxsplit=1)[0]

    # 2) strip trailing index-like suffixes (both underscore and plain forms)
    #    e.g., "_of_12", " of 12", "_12", "-12", " 12" at the end
    k = re.sub(r"(?:_of_\d+|(?:\s|_)of\s+\d+|_[0-9]+|-[0-9]+|\s+[0-9]+)$", "", k, flags=re.IGNORECASE)

    # 3) strip any remaining trailing " of <anything>" clause
    #    e.g., "fetched document sections of 3 docs" -> "fetched document sections"
    k = re.sub(r"\s+of\b.*$", "", k, flags=re.IGNORECASE)

    # 4) collapse whitespace to single spaces
    k = re.sub(r"\s+", " ", k).strip()

    # 5) lower-case for consistent merging (keeps the words, only case-folds)
    k = k.lower()

    return k



# ----------------------------
# Structure skeleton builder
# ----------------------------
# Replace values with:
#   - "" for primitives (string/number/boolean/null)
#   - [] for arrays of primitives
#   - [ {merged union} ] for arrays of objects
#   - {} for objects (with recursively processed children)
#
# Arrays: MergeKeys mode — union of keys across elements.

def _merge_nodes(a: Any, b: Any) -> Any:
    if isinstance(a, dict) and isinstance(b, dict):
        return _deep_merge_full(a, b)
    if isinstance(a, list) and isinstance(b, list):
        # arrays should contain either one representative dict element or be []
        if a and isinstance(a[0], dict) and b and isinstance(b[0], dict):
            return [ _deep_merge_full(a[0], b[0]) ]
        if a and isinstance(a[0], dict):
            return a
        if b and isinstance(b[0], dict):
            return b
        return []  # both primitive arrays collapse to []
    # prefer structured node
    if isinstance(a, (dict, list)) and not isinstance(b, (dict, list)):
        return a
    if isinstance(b, (dict, list)) and not isinstance(a, (dict, list)):
        return b
    # primitives -> ""
    return ""

def _deep_merge_full(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge_full(out[k], v)
        else:
            out[k] = v
    return out

def _primitive_skeleton(value: Any) -> Any:
    # per project choice: everything primitive -> ""
    return ""

def _list_skeleton(items: List[Any]) -> Any:
    if not items:
        return []
    object_skeletons: List[Dict[str, Any]] = []
    for it in items:
        sk = _build_skeleton(it)
        if isinstance(sk, dict):
            object_skeletons.append(sk)
    if object_skeletons:
        merged: Dict[str, Any] = {}
        for obj in object_skeletons:
            merged = _deep_merge_full(merged, obj)
        return [merged]
    # array of primitives
    return []

def _dict_skeleton(d: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for raw_k, v in d.items():
        k = normalize_key(raw_k)
        sk = _build_skeleton(v)
        if k in out:
            out[k] = _merge_nodes(out[k], sk)
        else:
            out[k] = sk
    return out

def _build_skeleton(node: Any) -> Any:
    if isinstance(node, dict):
        return _dict_skeleton(node)
    if isinstance(node, list):
        return _list_skeleton(node)
    # primitives (str/int/float/bool/None)
    return _primitive_skeleton(node)


def build_skeleton_from_json(sample_text: str) -> Dict[str, Any]:
    """
    Deterministic: parse JSON text, walk the tree, return a full structural skeleton
    with normalized keys and merged array-object shapes. ALWAYS returns a dict (object)
    when top-level is an object; if top-level is an array, return {"__root__": [merged]}.
    """
    data = json.loads(sample_text)

    if isinstance(data, dict):
        return _dict_skeleton(data)

    if isinstance(data, list):
        # wrap top-level arrays under a synthetic root
        return {"__root__": _list_skeleton(data)}

    # unusual primitive top-level -> return as "__value__"
    return {"__value__": _primitive_skeleton(data)}
    