# ADR-007: GitHub Actions as CI/CD Platform

## Document Control

| Field | Detail |
|---|---|
| **ADR ID** | ADR-007 |
| **Title** | GitHub Actions as CI/CD Platform |
| **Status** | Accepted |
| **Author** | Praveen Mittal |
| **Date** | 2026-06-30 |
| **Deciders** | AI Solution Architect, ARB |

---

## Context

The project requires automated quality gates, container build and scan pipelines, and environment promotion workflows co-located with the source code repository.

---

### Options Considered

| Option | Pros | Cons |
|---|---|---|
| **GitHub Actions** | Native to GitHub; no separate CI server; rich marketplace of actions; GPU runners available | Vendor lock-in to GitHub |
| Jenkins | Highly flexible; self-hosted | Significant operational overhead; plugin maintenance burden |
| GitLab CI | Strong built-in CI/CD | Requires GitLab hosting or migration |
| CircleCI | Good DX; fast | Additional SaaS dependency; cost |

### Decision

**GitHub Actions** using workflow files in `.github/workflows/`.

### Rationale

- Source code already on GitHub — zero additional tooling to adopt
- GPU-enabled runners available for model evaluation gates
- Marketplace actions for Docker build, security scanning (Trivy), secret scanning (Gitleaks), and Helm linting
- Workflow files committed to git — pipeline changes are versioned and reviewable

### Consequences

- **Positive**: Zero additional infrastructure; reproducible pipeline as code; rich action ecosystem
- **Negative**: GitHub vendor dependency; self-hosted runner needed for GPU gates
- **Neutral**: Workflow files structured per environment: `ci.yml` (PR), `cd-staging.yml`, `cd-production.yml`

---

## Status

**Accepted**

---

## References

- [04_SAD.md](../04_SAD.md)
- [02_BRD.md](../../Phase-1/02_BRD.md)
- [01_Architecture_Vision.md](../../Phase-0/01_Architecture_Vision.md)
