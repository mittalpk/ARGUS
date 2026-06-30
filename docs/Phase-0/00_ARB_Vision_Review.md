# ARGUS: ARB Vision Review Pack
## Architecture Review Board — Phase 0 Gate

## Document Control

| Field | Detail |
|---|---|
| **Document ID** | 00_ARB_Vision_Review |
| **Version** | 1.0 |
| **Status** | Draft — Pending ARB Review |
| **Author** | Praveen Mittal |
| **ARB Chair** | [NAME] |
| **Review Date** | [INSERT DATE] |
| **Meeting Link** | [INSERT] |

---

## 1. Purpose

This document constitutes the formal presentation pack for the Architecture Review Board (ARB) Phase 0 Vision Review. The ARB must review and approve this material before Project ARGUS proceeds to Phase 1.

---

## 2. Review Agenda

| # | Topic | Owner | Duration |
|---|---|---|---|
| 1 | Business context and project objectives | Project Lead | 10 min |
| 2 | Scope — in-scope and out-of-scope | Project Lead | 5 min |
| 3 | Architecture vision — baseline vs. target state | AI Architect | 15 min |
| 4 | Technology stack rationale | AI Architect | 10 min |
| 5 | Compliance framing | Compliance Lead | 10 min |
| 6 | Risks and constraints | Project Manager | 10 min |
| 7 | ARB questions and challenge | ARB Chair | 15 min |
| 8 | Decision and conditions | ARB Chair | 5 min |

**Total Duration**: ~80 minutes

---

## 3. Phase 0 Deliverables Presented

| Document | Status | Location |
|---|---|---|
| Project Charter | Draft | [00_Project_Charter.md](00_Project_Charter.md) |
| Architecture Vision | Draft | [01_Architecture_Vision.md](01_Architecture_Vision.md) |
| Stakeholder Matrix | Draft | [00_Stakeholder_Matrix.md](00_Stakeholder_Matrix.md) |
| RAID Log | Embedded in Charter | [00_Project_Charter.md](00_Project_Charter.md) |

---

## 4. Architecture Vision Summary

ARGUS is a production-grade identity document fraud detection system targeting three attack vectors: physical manipulation, GenAI-driven digital edits, and print-and-capture recapture attacks.

### Target Architecture Pillars

| Pillar | Design Choice |
|---|---|
| ML | Ensemble of EVA-02-Large, ConvNeXt-V2-Base, EfficientNet-B4 trained with PyTorch + timm |
| Serving | FastAPI inference API in Docker, orchestrated via Kubernetes |
| MLOps | DVC + Hydra + MLflow for reproducible pipelines and model registry |
| Observability | Prometheus + Grafana + Evidently AI for system and model monitoring |
| CI/CD | GitHub Actions with mandatory quality gates |
| Compliance | EU AI Act high-risk controls, GDPR data minimisation, ISO/IEC 42001 management system |

### Key Architecture Principles Under Review

- Reproducibility by default
- Security and compliance by design
- Modularity and independent testability
- Human oversight for low-confidence predictions
- Full rollback capability within minutes of any release

---

## 5. ARB Review Criteria

The ARB must evaluate the Architecture Vision against the following criteria:

| Criterion | Question |
|---|---|
| Strategic alignment | Does the target architecture support the stated business objectives and competition goals? |
| Feasibility | Is the technology stack achievable within the timeline and budget constraints? |
| Compliance | Are EU AI Act, GDPR, and ISO/IEC 42001 obligations adequately addressed from Phase 0? |
| Risk management | Are the key architecture risks identified and mitigations credible? |
| Completeness | Does the vision sufficiently scope the work for Phase 1 requirements definition? |
| Governance | Is the RACI, ARB involvement, and gate structure appropriate? |

---

## 6. Open Questions for ARB

| # | Question | Raised By |
|---|---|---|
| Q-01 | Is the EU AI Act classification as High-Risk confirmed, given biometric-adjacent processing? | Compliance Lead |
| Q-02 | Should EVA-02-Large be provisionally excluded due to inference latency risk until benchmarked? | ARB |
| Q-03 | Is Kubernetes hosting confirmed, or should serverless container alternatives be evaluated? | Infra Lead |
| Q-04 | Will self-hosted MLflow satisfy audit evidence requirements or is a managed service needed? | Compliance Lead |

---

## 7. ARB Decision Options

| Decision | Meaning |
|---|---|
| ✅ **Approved** | Architecture Vision is accepted. Phase 1 may proceed immediately. |
| ✅ **Approved with Conditions** | Phase 1 may proceed but named conditions must be resolved by Phase 2 ARB review. |
| 🔁 **Revision Required** | Specific sections must be revised before Phase 1 can begin. |
| ❌ **Not Approved** | Fundamental concerns prevent Phase 1 from starting. Escalation required. |

---

## 8. ARB Decision Record

**Decision**: ☐ Approved &nbsp; ☐ Approved with Conditions &nbsp; ☐ Revision Required &nbsp; ☐ Not Approved

**Conditions / Actions Required** (if applicable):

| # | Condition | Owner | Due Date |
|---|---|---|---|
| | | | |
| | | | |

**ARB Comments**:

> *[To be completed during the review meeting]*

---

## 9. Phase 0 Exit Checklist Confirmation

| Criterion | Confirmed |
|---|---|
| Project Charter signed by sponsor | ☐ |
| Architecture Vision reviewed and approved by ARB | ☐ |
| Stakeholder matrix reviewed | ☐ |
| Initial RAID log created | ☐ |
| Phase 1 owner and start date confirmed | ☐ |

---

## 10. Sign-Off

By signing below, the ARB confirms Phase 0 is complete and Project ARGUS is authorised to proceed to Phase 1.

| Name | Role | Decision | Signature | Date |
|---|---|---|---|---|
| [Name] | ARB Chair | | | |
| [Name] | Security Lead | | | |
| [Name] | Compliance Lead | | | |
| Praveen Mittal | AI Solution Architect | | | |
| [Name] | Business Sponsor | | | |
