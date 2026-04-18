from __future__ import annotations

import sys
from pathlib import Path


def ensure_vendor_paths() -> None:
    """Make vendored third-party packages importable from this repository."""
    repo_root = Path(__file__).resolve().parents[2]
    vendor_roots = (
        repo_root / "3rd_party" / "pyssp_standard",
        repo_root / "3rd_party" / "pyfmu_csv" / "python",
    )

    for root in vendor_roots:
        root_str = str(root)
        if root.exists() and root_str not in sys.path:
            sys.path.insert(0, root_str)

