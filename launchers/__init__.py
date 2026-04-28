"""Top-level launchers for SopaDeOtoe backtest and portfolio runs.

Named `launchers/` (not `scripts/`) intentionally: v12 has its own
top-level `scripts/` package, and having one here would shadow it via
sys.path ordering and break `from scripts._gmm_features import ...`.
"""
