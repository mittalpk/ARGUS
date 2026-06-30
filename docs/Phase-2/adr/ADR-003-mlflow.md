# ADR-003: MLflow for Experiment Tracking and Model Registry

## Document Control

| Field | Detail |
|---|---|
| **ADR ID** | ADR-003 |
| **Title** | MLflow for Experiment Tracking and Model Registry |
| **Status** | Accepted |
| **Author** | Praveen Mittal |
| **Date** | 2026-06-30 |
| **Deciders** | AI Solution Architect, ARB |

---

## Context

The project requires reproducible experiment tracking, artifact storage, and a model promotion lifecycle from candidate to production.

---

### Options Considered

| Option | Pros | Cons |
|---|---|---|
| **MLflow** | Self-hostable; built-in model registry; strong PyTorch integration; audit-friendly | UI is functional but not polished |
| Weights & Biases (W&B) | Best-in-class UI; strong team collaboration features | SaaS dependency; data leaves team control; cost at scale |
| Neptune.ai | Good UI; flexible | SaaS; cost; less common in enterprise regulated environments |
| Custom logging to S3 | Full control | No registry, no UI, high maintenance burden |

### Decision

**MLflow** (self-hosted or managed cloud service — see OA-03).

### Rationale

- Self-hostable option keeps all experiment data and model artifacts within the team's control — important for compliance
- Model Registry provides the champion-challenger lifecycle required by FR-22
- Native PyTorch artifact logging reduces integration overhead
- Audit logs of model promotions satisfy EU AI Act post-market monitoring requirements

### Consequences

- **Positive**: Full data sovereignty; registry lifecycle matches runbook governance model; no SaaS cost
- **Negative**: Team must operate MLflow server (or use managed equivalent)
- **Open**: OA-03 — confirm self-hosted vs. managed cloud MLflow before Phase 3

---

## Status

**Accepted**

---

## References

- [04_SAD.md](../04_SAD.md)
- [02_BRD.md](../../Phase-1/02_BRD.md)
- [01_Architecture_Vision.md](../../Phase-0/01_Architecture_Vision.md)
