# ADR-006: Kubernetes as Container Orchestration Platform

## Document Control

| Field | Detail |
|---|---|
| **ADR ID** | ADR-006 |
| **Title** | Kubernetes as Container Orchestration Platform |
| **Status** | Accepted |
| **Author** | Praveen Mittal |
| **Date** | 2026-06-30 |
| **Deciders** | AI Solution Architect, ARB |

---

## Context

The production inference service must meet 99.5% availability, support horizontal scaling, enable zero-downtime blue-green deployments, and provide health probe integration.

---

### Options Considered

| Option | Pros | Cons |
|---|---|---|
| **Kubernetes (managed)** | Industry standard; HPA for autoscaling; rolling/blue-green deployments; liveness probes built-in | Operational complexity; requires infra expertise |
| Docker Compose | Simple | Not production-grade; no autoscaling; no health management |
| AWS Lambda / Cloud Run | Serverless; low ops burden | Cold start latency unacceptable for p95 < 800 ms SLO; GPU support limited |
| Nomad | Simpler than Kubernetes | Smaller ecosystem; less tooling |

### Decision

**Managed Kubernetes** (provider to be confirmed — see OA-02: AWS EKS / GCP GKE / Azure AKS).

### Rationale

- Managed Kubernetes eliminates control plane management burden
- HPA (Horizontal Pod Autoscaler) satisfies NFR-02 throughput scaling requirement
- Liveness and readiness probes integrate directly with FR-13 API health endpoints
- Blue-green deployment pattern (defined in runbook) is natively supported via Kubernetes Service switching
- RBAC, network policies, and namespace isolation satisfy security NFRs

### Consequences

- **Positive**: Enterprise-grade availability; autoscaling; zero-downtime deployments; strong security posture
- **Negative**: Requires Kubernetes expertise in the team; cloud cost for cluster
- **Open**: OA-02 — confirm provider and cluster sizing before Phase 4

---

## Status

**Accepted**

---

## References

- [04_SAD.md](../04_SAD.md)
- [02_BRD.md](../../Phase-1/02_BRD.md)
- [01_Architecture_Vision.md](../../Phase-0/01_Architecture_Vision.md)
