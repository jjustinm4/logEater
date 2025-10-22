import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .file_discovery import discover_files, DEFAULT_EXTS

@dataclass
class MatchLine:
    line: int
    text: str

@dataclass
class FileMatch:
    file: str
    matches: List[MatchLine] = field(default_factory=list)

@dataclass
class SearchResult:
    matched: List[FileMatch] = field(default_factory=list)
    not_matched: List[str] = field(default_factory=list)

class SearchService:
    """
    Phase-1 static search engine:
    - keyword / regex
    - AND / OR / Single pattern
    - case sensitivity
    - recursive scan with extension filter
    - line preview with line numbers
    """
    MAX_PREVIEW_PER_FILE = 10  # cap previews per file

    def __init__(self, include_exts: Optional[List[str]] = None):
        self.include_exts = set(include_exts or DEFAULT_EXTS)

    def _compile_patterns(
        self,
        pattern_input: str,
        logic_mode: str,
        use_regex: bool,
        case_sensitive: bool
    ) -> Tuple[List[re.Pattern], str]:
        """
        Returns list of compiled patterns and normalized logic mode.
        For AND/OR, patterns are split by comma.
        """
        flags = 0 if case_sensitive else re.IGNORECASE
        logic_mode = (logic_mode or "Single Pattern").strip()

        if logic_mode in ("AND", "OR"):
            raw_parts = [p.strip() for p in pattern_input.split(",") if p.strip()]
            if not raw_parts:
                raw_parts = [pattern_input.strip()]
        else:
            raw_parts = [pattern_input.strip()]

        compiled: List[re.Pattern] = []
        for pat in raw_parts:
            if not use_regex:
                pat = re.escape(pat)
            try:
                compiled.append(re.compile(pat, flags))
            except re.error as e:
                raise ValueError(f"Invalid regex: {pat} ({e})")
        return compiled, logic_mode

    def _line_matches(
        self,
        line: str,
        patterns: List[re.Pattern],
        logic_mode: str
    ) -> bool:
        if logic_mode == "AND":
            return all(p.search(line) is not None for p in patterns)
        elif logic_mode == "OR":
            return any(p.search(line) is not None for p in patterns)
        else:
            # Single Pattern
            return patterns[0].search(line) is not None

    def search(
        self,
        folder: str,
        pattern_input: str,
        logic_mode: str = "Single Pattern",
        use_regex: bool = False,
        case_sensitive: bool = False,
    ) -> SearchResult:
        """
        Perform the search and return structured results.
        """
        if not pattern_input or not pattern_input.strip():
            return SearchResult()

        patterns, logic_mode = self._compile_patterns(
            pattern_input=pattern_input,
            logic_mode=logic_mode,
            use_regex=use_regex,
            case_sensitive=case_sensitive
        )

        files = discover_files(folder, include_exts=self.include_exts)
        result = SearchResult()

        for fpath in files:
            matches: List[MatchLine] = []
            try:
                with fpath.open("r", encoding="utf-8", errors="ignore") as f:
                    for idx, line in enumerate(f, start=1):
                        if self._line_matches(line, patterns, logic_mode):
                            matches.append(MatchLine(line=idx, text=line.rstrip("\n")))
                            if len(matches) >= self.MAX_PREVIEW_PER_FILE:
                                break
            except Exception:
                # If file can't be read, treat as not matched (but don't crash)
                result.not_matched.append(str(fpath))
                continue

            if matches:
                result.matched.append(FileMatch(file=str(fpath), matches=matches))
            else:
                result.not_matched.append(str(fpath))

        return result
