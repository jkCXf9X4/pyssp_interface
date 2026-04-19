from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
PATH_ENTRIES = (
    REPO_ROOT / "src",
    REPO_ROOT / "3rd_party" / "pyssp_standard",
    REPO_ROOT / "3rd_party" / "pyfmu_csv" / "python",
)

for entry in PATH_ENTRIES:
    entry_str = str(entry)
    if entry.exists() and entry_str not in sys.path:
        sys.path.insert(0, entry_str)
