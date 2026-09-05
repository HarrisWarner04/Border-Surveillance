"""conftest.py — adds ibvap_contracts src to sys.path for pytest."""

from __future__ import annotations

import sys
from pathlib import Path

# contracts/src contains the ibvap_contracts package
_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
