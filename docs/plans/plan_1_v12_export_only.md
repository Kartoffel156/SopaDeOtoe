# Plan 1 de 5: ~~v12 `export_only` mode~~ ELIMINADO

> **Este plan fue eliminado.** La logica de export se movio a `SopaDeOtoe/core/worker.py`
> (Plan 2 revisado) para evitar tocar el repo hermano `StrategyParrot/v12`.
>
> Ver Plan 2 para la implementacion completa.

## Razon del cambio

- `StrategyParrot/v12` es un repo git separado (branch `master`)
- `feature/meta-pool-conjunto` solo existe en SopaDeOtoe
- Modificar `v12/main.py` requeriria coordinar 2 repos y 2 branches
- `worker.py` ya tiene el precedente `run_signal_check()` que corre M1-M3 inline sin llamar a `main.run()`
- Extender ese patron a M1-M4 + meta-features es natural y mantiene todo en un solo repo
