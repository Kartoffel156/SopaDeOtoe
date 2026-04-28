"""
Path setup -- connects SopaDeOtoe to the pipeline (StrategyParrot/v12/).

Every module in SopaDeOtoe that needs pipeline access starts with:
    import SopaDeOtoe._path_setup  # noqa: F401

Layout (relative discovery, no env vars or hardcoded absolutes):
    Patacon/
    ├── SopaDeOtoe/        <-- this file is in here
    └── StrategyParrot/
        └── v12/           <-- the pipeline
"""

import sys
from pathlib import Path

_SOPA_DIR = Path(__file__).parent                              # SopaDeOtoe/
_PATACON_DIR = _SOPA_DIR.parent                                # Patacon/
_STRATEGY_PARROT_DIR = _PATACON_DIR / "StrategyParrot"         # StrategyParrot/
_PIPELINE_DIR = _STRATEGY_PARROT_DIR / "v12"                   # v12/

for _p in (_PIPELINE_DIR, _STRATEGY_PARROT_DIR, _PATACON_DIR, _SOPA_DIR):
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)
