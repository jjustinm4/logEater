from pathlib import Path
from typing import Iterable, List, Set

DEFAULT_EXTS: Set[str] = {".log", ".txt", ".json"}

def discover_files(root_dir: str, include_exts: Iterable[str] = DEFAULT_EXTS) -> List[Path]:
    """
    Recursively discover files under root_dir limited to include_exts.
    Returns a list of pathlib.Path objects.
    """
    root = Path(root_dir).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return []

    include_exts = {ext.lower() for ext in include_exts}
    files: List[Path] = []
    for p in root.rglob("*"):
        if p.is_file():
            if p.suffix.lower() in include_exts:
                files.append(p)
    return files
