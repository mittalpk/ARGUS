# ADR-005: Hydra for Experiment Configuration Management

## Document Control

| Field | Detail |
|---|---|
| **ADR ID** | ADR-005 |
| **Title** | Hydra for Experiment Configuration Management |
| **Status** | Accepted |
| **Author** | Praveen Mittal |
| **Date** | 2026-06-30 |
| **Deciders** | AI Solution Architect, ARB |

---

## Context

Training experiments require composable, overridable configurations for model architecture, hyperparameters, augmentation settings, and infrastructure parameters without hardcoding values.

---

### Options Considered

| Option | Pros | Cons |
|---|---|---|
| **Hydra** | Composable config groups; CLI overrides; multi-run sweeps; integrates with MLflow | Learning curve for composition syntax |
| Plain YAML + argparse | Simple | No composition; no sweep support; fragile at scale |
| ConfigParser | Familiar | Not suitable for nested ML configs |
| Pydantic settings | Strong typing | Not designed for composable experiment configs |

### Decision

**Hydra** (latest stable) with config groups structured as `configs/model/`, `configs/training/`, `configs/inference/`.

### Rationale

- Composable config groups allow `python train.py model=eva02_large training=full_run` without code changes
- Multi-run sweep mode supports hyperparameter search without a separate sweep framework
- Config is automatically logged to MLflow, satisfying FR-20 reproducibility requirements
- CLI override pattern (`+model.lr=0.001`) enables rapid experimentation

### Consequences

- **Positive**: Clean separation of code and config; reproducible experiments; sweeps without extra tooling
- **Negative**: Hydra's composition syntax requires team familiarisation
- **Neutral**: All config files committed to git under `configs/`

---

## Status

**Accepted**

---

## References

- [04_SAD.md](../04_SAD.md)
- [02_BRD.md](../../Phase-1/02_BRD.md)
- [01_Architecture_Vision.md](../../Phase-0/01_Architecture_Vision.md)
