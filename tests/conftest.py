from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

src_root_str = str(SRC_ROOT)
if src_root_str not in sys.path:
    sys.path.insert(0, src_root_str)

