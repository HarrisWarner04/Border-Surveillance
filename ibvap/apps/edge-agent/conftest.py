"""
conftest.py — pytest root configuration for edge-agent.

Adds the edge-agent root directory and the contracts package to sys.path
so that `import src.X` and `import ibvap_contracts` both work regardless
of the current working directory when pytest is invoked.

pytest discovers this file automatically because it is at the testpaths root.
"""

from __future__ import annotations

import sys
from pathlib import Path

# edge-agent root  (contains src/, tests/, configs/, etc.)
_EDGE_AGENT_ROOT = Path(__file__).parent
# ibvap_contracts package
_CONTRACTS_SRC = _EDGE_AGENT_ROOT.parents[1] / "packages" / "contracts" / "src"

for _p in [str(_EDGE_AGENT_ROOT), str(_CONTRACTS_SRC)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
