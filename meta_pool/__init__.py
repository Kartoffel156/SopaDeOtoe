"""
meta_pool — Pooled meta-model training across graduated strategies.

Consumes parquets from results/exploration/meta_datasets/<strategy>/
(produced by worker.py --mode export) and trains a single walk-forward
OOS meta-model on the combined dataset.

Modules:
  dataset  — load, validate, pool meta-datasets
  trainer  — walk-forward OOS training + null model
  gating   — probability → sized positions (bet sizing pipeline)
  replay   — backtest positions → StrategyResult for Layer 2
"""
