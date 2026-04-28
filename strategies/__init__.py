"""
Official (graduated) strategies registry.

Each graduated strategy file in this directory must:
  1. Start with `import SopaDeOtoe._path_setup  # noqa: F401`
  2. Subclass `BaseStrategy` from `src.strategy` (v12)
  3. Be re-exported here so importing `SopaDeOtoe.strategies` triggers
     auto-registration in `BaseStrategy._REGISTRY`.

Example (after a strategy is promoted from Strategy_lab):
    from SopaDeOtoe.strategies.HypothesisH109BollingerLongOnly import (
        HypothesisH109BollingerLongOnly,
    )
"""

import SopaDeOtoe._path_setup  # noqa: F401

# Graduated strategies — append imports here as strategies are promoted.

# Graduated 2026-04-11 (first cohort, 7 strategies).
from SopaDeOtoe.strategies.HypothesisH72AsymmetricRSIDrawdownShield import (  # noqa: F401
    HypothesisH72AsymmetricRSIDrawdownShield,
)
from SopaDeOtoe.strategies.HypothesisH86WonhamMarkovRefinado import (  # noqa: F401
    HypothesisH86WonhamMarkovRefinado,
)
from SopaDeOtoe.strategies.HypothesisH136GoldenDeathCrossAsym import (  # noqa: F401
    HypothesisH136GoldenDeathCrossAsym,
)
from SopaDeOtoe.strategies.HypothesisH236MomentumReversalAsym import (  # noqa: F401
    HypothesisH236MomentumReversalAsym,
)
from SopaDeOtoe.strategies.HypothesisH371MaxMinDualTriggerFreq import (  # noqa: F401
    HypothesisH371MaxMinDualTriggerFreq,
)
from SopaDeOtoe.strategies.HypothesisH426RSIGarchBullBear import (  # noqa: F401
    HypothesisH426RSIGarchBullBear,
)
from SopaDeOtoe.strategies.HypothesisH434MaxMinDualHorizon import (  # noqa: F401
    HypothesisH434MaxMinDualHorizon,
)
from SopaDeOtoe.strategies.HypothesisH481GoldenCrossPSAR import (  # noqa: F401
    HypothesisH481GoldenCrossPSAR,
)

# Graduated 2026-04-19 (second cohort, 9 strategies from Strategy_lab).
from SopaDeOtoe.strategies.TSIMeanReversion import (  # noqa: F401
    TSIMeanReversion,
)
from SopaDeOtoe.strategies.HypothesisH110BollingerKyleGate import (  # noqa: F401
    HypothesisH110BollingerKyleGate,
)
from SopaDeOtoe.strategies.HypothesisH203VolExpansionEntry import (  # noqa: F401
    HypothesisH203VolExpansionEntry,
)
from SopaDeOtoe.strategies.HypothesisH167BollingerRangingOFIGate import (  # noqa: F401
    HypothesisH167BollingerRangingOFIGate,
)
from SopaDeOtoe.strategies.HypothesisH318TrendlineChannelSqueeze import (  # noqa: F401
    HypothesisH318TrendlineChannelSqueeze,
)
from SopaDeOtoe.strategies.HypothesisH37DynamicGridInformedGate import (  # noqa: F401
    HypothesisH37DynamicGridInformedGate,
)
from SopaDeOtoe.strategies.DualMovingAverageCrossover import (  # noqa: F401
    DualMovingAverageCrossover,
)
from SopaDeOtoe.strategies.MultiTimeframeTrendSignal import (  # noqa: F401
    MultiTimeframeTrendSignal,
)
