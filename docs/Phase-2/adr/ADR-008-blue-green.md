# ADR-008: Blue-Green Deployment as Production Release Strategy

## Document Control

| Field | Detail |
|---|---|
| **ADR ID** | ADR-008 |
| **Title** | Blue-Green Deployment as Production Release Strategy |
| **Status** | Accepted |
| **Author** | Praveen Mittal |
| **Date** | 2026-06-30 |
| **Deciders** | AI Solution Architect, ARB |

---

## Context

Production model updates must support zero-downtime deployments with immediate rollback capability. The runbook defines a rollback SLA of under 5 minutes for Sev 1 incidents.

---

### Options Considered

| Option | Pros | Cons |
|---|---|---|
| **Blue-Green** | Instant rollback by switching service selector; full production environment validated before cutover | Requires 2x infrastructure during transition |
| Rolling deployment | Lower resource cost | Partial rollout means mixed versions in production simultaneously; rollback is slower |
| Canary deployment (only) | Gradual risk exposure | Cannot instantly roll back; partial traffic on new version creates mixed-signal monitoring |
| Recreate | Simple | Causes downtime; unacceptable for 99.5% SLO |

### Decision

**Blue-Green deployment** with an optional canary traffic ramp (5% → 25% → 50% → 100%) during the transition window before full blue-green cutover.

### Rationale

- Instant rollback (< 2 minutes) is achieved by switching the Kubernetes Service selector back to the blue deployment
- Full production environment is validated on green before any user traffic — eliminates "it works in staging" failures
- Canary ramp during transition provides early signal on real traffic before full cutover
- Aligns directly with runbook rollback procedure and Sev 1 response SLA

### Consequences

- **Positive**: Zero-downtime; < 2 min rollback; full environment validation before cutover
- **Negative**: Temporary 2x compute cost during blue-green transition window (typically < 30 min)
- **Neutral**: Blue environment kept warm until release closure window completes (typically 24 hours post-release)

---

## Status

**Accepted**

---

## References

- [04_SAD.md](../04_SAD.md)
- [02_BRD.md](../../Phase-1/02_BRD.md)
- [01_Architecture_Vision.md](../../Phase-0/01_Architecture_Vision.md)
