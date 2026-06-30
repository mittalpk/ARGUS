# ARGUS: Solution Architecture Document (SAD)
## TOGAF ADM Phase B, C, D

## Document Control

| Field | Detail |
|---|---|
| **Document ID** | 04_SAD |
| **Version** | 1.0 |
| **Status** | Draft |
| **Author** | Praveen Mittal |
| **Reviewer** | ARB, Security Lead, Infrastructure Lead |
| **Date Created** | 2026-06-30 |
| **Last Updated** | 2026-06-30 |
| **Related Docs** | [01_Architecture_Vision.md](../Phase-0/01_Architecture_Vision.md), [02_BRD.md](../Phase-1/02_BRD.md), [05_DAD.md](05_DAD.md) |

---

## 1. Purpose

This document defines the complete solution architecture for Project ARGUS, covering the business, data, application, and technology architecture layers (TOGAF Phases B, C, D). It is the authoritative design reference for all development, deployment, and operational decisions.

---

## 2. Architecture Principles (Reaffirmed)

| # | Principle |
|---|---|
| P-01 | Reproducibility by default — every run traceable from data to artifact |
| P-02 | Security and compliance by design |
| P-03 | Modularity — every component independently testable and replaceable |
| P-04 | Observability — every decision measurable and traceable |
| P-05 | Reversibility — every deployment rollback-capable within minutes |
| P-06 | Data minimisation — PII stripped at ingestion |
| P-07 | Human oversight — low-confidence predictions routed to human review |

---

## 3. System Context

```
┌──────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL ACTORS                             │
│                                                                      │
│   API Consumer          Competition Platform        Compliance Auditor│
│        │                       │                          │          │
└────────┼───────────────────────┼──────────────────────────┼──────────┘
         │                       │                          │
         ▼                       ▼                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         ARGUS SYSTEM BOUNDARY                        │
│                                                                      │
│  ┌─────────────┐   ┌──────────────┐   ┌────────────────────────┐   │
│  │  Ingestion  │──▶│  ML Pipeline │──▶│   Inference API Layer  │   │
│  │  & Data     │   │  Training &  │   │   FastAPI + Container  │   │
│  │  Pipeline   │   │  Registry    │   │                        │   │
│  └─────────────┘   └──────────────┘   └────────────────────────┘   │
│          │                │                        │                 │
│          └────────────────┴────────────────────────┘                 │
│                                    │                                 │
│                    ┌───────────────▼──────────────┐                 │
│                    │   MLOps & Observability Layer │                 │
│                    │   CI/CD · Registry · Monitor  │                 │
│                    └──────────────────────────────┘                 │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. Business Architecture (Phase B)

### 4.1 Business Capabilities

| Capability | Description |
|---|---|
| Document Fraud Detection | Classify identity documents across three attack vectors |
| Explainable AI | Return confidence scores and attention maps with every prediction |
| Human Review Escalation | Route low-confidence or ambiguous predictions to human reviewers |
| Model Governance | Champion-challenger evaluation and formal model promotion |
| Audit and Compliance | Structured logging, evidence retention, regulatory reporting |
| Continuous Improvement | Drift detection, retraining, and model refresh lifecycle |

### 4.2 Business Process Flow

```
Submit Document
      │
      ▼
Validate Input ──(invalid)──▶ Return Error (HTTP 422)
      │
      ▼
Preprocess Image (resize, normalise, EXIF strip)
      │
      ▼
Ensemble Inference (EVA-02 + ConvNeXt-V2 + EfficientNet-B4)
      │
      ▼
Score Aggregation
      │
   ┌──┴──────────────────────────┐
   │ confidence < threshold?     │
   Yes                          No
   │                             │
   ▼                             ▼
Flag: requires_human_review   Return Result
Route to human review queue   Log to audit store
```

---

## 5. Data Architecture (Phase C — Information)

> See [05_DAD.md](05_DAD.md) for full data architecture. Summary below.

| Layer | Detail |
|---|---|
| Source | FREUID Challenge 2026 dataset (Kaggle) |
| Ingestion | Kaggle API → local `data/` directory |
| Preprocessing | Resize to 224×224 (EfficientNet) or 448×448 (EVA-02, ConvNeXt); normalise; EXIF strip |
| Augmentation | Random flip, rotate, colour jitter, cutout (training only) |
| Versioning | DVC — dataset hash locked per experiment run |
| Splits | 70% train / 15% validation / 15% test — deterministic seed |
| Storage | Local filesystem (dev/test); cloud object store (staging/production) |

---

## 6. Application Architecture (Phase C — Application)

### 6.1 Component Map

```
┌──────────────────────────────────────────────────────────────┐
│                     ARGUS APPLICATION LAYER                  │
│                                                              │
│  ┌────────────────┐   ┌──────────────────────────────────┐  │
│  │ src/data/      │   │ src/models/                      │  │
│  │ ─ ingestion.py │   │ ─ eva02.py                       │  │
│  │ ─ preprocess.py│   │ ─ convnext_v2.py                 │  │
│  │ ─ augment.py   │   │ ─ efficientnet_b4.py             │  │
│  │ ─ dataset.py   │   │ ─ ensemble.py                    │  │
│  └────────────────┘   └──────────────────────────────────┘  │
│                                                              │
│  ┌────────────────┐   ┌──────────────────────────────────┐  │
│  │ src/training/  │   │ src/api/                         │  │
│  │ ─ train.py     │   │ ─ main.py (FastAPI app)          │  │
│  │ ─ evaluate.py  │   │ ─ routes/classify.py             │  │
│  │ ─ registry.py  │   │ ─ routes/health.py               │  │
│  │ ─ callbacks.py │   │ ─ schemas.py                     │  │
│  └────────────────┘   │ ─ middleware/logging.py          │  │
│                       └──────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ configs/  (Hydra)                                    │   │
│  │ ─ model/efficientnet_b4.yaml                        │   │
│  │ ─ model/eva02_large.yaml                            │   │
│  │ ─ model/convnext_v2_base.yaml                       │   │
│  │ ─ training/default.yaml                             │   │
│  │ ─ inference/default.yaml                            │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 API Specification

**Base URL**: `https://api.argus.internal/v1`

#### POST /classify

Classify a single document image.

**Request**:
```json
{
  "image": "<base64-encoded image or multipart/form-data>",
  "image_format": "jpeg | png",
  "request_id": "<optional UUID>"
}
```

**Response (200)**:
```json
{
  "request_id": "uuid-v4",
  "result": "genuine | fraud",
  "fraud_score": 0.92,
  "confidence": 0.88,
  "requires_human_review": false,
  "attention_map_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "model_version": "v1.3.0",
  "latency_ms": 340
}
```

**Error Responses**:

| HTTP Code | Error Code | Condition |
|---|---|---|
| 413 | `IMAGE_TOO_LARGE` | Image > 10 MB |
| 422 | `INVALID_IMAGE_FORMAT` | Not JPEG or PNG |
| 422 | `CORRUPT_IMAGE` | Binary corruption detected |
| 422 | `BATCH_SIZE_EXCEEDED` | Batch > 32 images |
| 503 | `INFERENCE_TIMEOUT` | Inference exceeded internal timeout |
| 503 | `SERVICE_UNAVAILABLE` | Dependency unavailable |

#### POST /classify/batch

Classify up to 32 documents in one request. Returns array of results in input order.

#### GET /health

Returns `200 OK` when service is live.

#### GET /ready

Returns `200 OK` when model is loaded and ready to serve.

#### GET /docs

OpenAPI interactive documentation (FastAPI built-in).

### 6.3 Ensemble Architecture

```
Input Image
     │
     ├──▶ EVA-02-Large ──────────────▶ score_1 ─┐
     │                                           │
     ├──▶ ConvNeXt-V2-Base ────────────▶ score_2 ─┼──▶ Weighted Aggregator ──▶ fraud_score
     │                                           │
     └──▶ EfficientNet-B4 ────────────▶ score_3 ─┘
```

- **Aggregation method**: Learned weighted average (weights trained on validation set)
- **Fallback**: If EVA-02-Large exceeds latency budget, EfficientNet-B4 weight increases to maintain SLO

---

## 7. Technology Architecture (Phase D)

### 7.1 Full Technology Stack

| Layer | Component | Technology | Version Policy |
|---|---|---|---|
| ML Framework | Model training and inference | PyTorch | 2.3.1 (CUDA 12.1) |
| Backbone Library | Pre-trained models | timm | 1.0.3 |
| Config Management | Experiment configuration | Hydra | 1.3.2 |
| Data Versioning | Dataset and pipeline versioning | DVC | 3.51.0 |
| Experiment Tracking | Metrics, params, artifacts | MLflow | 2.14.1 |
| API Framework | Inference REST API | FastAPI + Uvicorn | 0.111.0 (Uvicorn 0.30.1) |
| Containerisation | Application packaging | Docker | 26.1.4 |
| Orchestration | Production deployment | Kubernetes | 1.30 |
| API Gateway | TLS, routing, rate limiting | NGINX / Cloud Gateway | Managed |
| CI/CD | Automated pipeline | GitHub Actions | N/A |
| Infrastructure as Code | Environment provisioning | Terraform + Helm | Terraform 1.8.5, Helm 3.15.1 |
| Metrics | System and model telemetry | Prometheus | 2.52.0 |
| Dashboards | Visualisation | Grafana | 11.0.0 |
| Logging | Structured log management | Structured JSON → CloudWatch / ELK | Managed |
| Drift Detection | Distribution monitoring | Evidently AI | 0.4.23 |
| Alerting | Incident notification | Grafana Alerts + PagerDuty | Managed |
| Secrets Management | Credential management | HashiCorp Vault / Cloud Secrets Manager | Managed |

### 7.2 Environment Topology

| Environment | Infrastructure | Data | Promotion |
|---|---|---|---|
| Dev | Local machine / single GPU VM | Synthetic / approved sample | Continuous |
| Test | CI runner + small GPU instance | Sanitised validation data | On merge to `main` |
| Staging | Kubernetes cluster (replica of prod) | Masked sanctioned data | Release candidate tag |
| Production | Kubernetes cluster, multi-node | Production access-controlled | Go/No-Go approval |

### 7.3 Network and Security Topology

```
Internet
   │
   ▼
[API Gateway / NGINX]
   │  TLS 1.2+
   ▼
[Kubernetes Ingress]
   │
   ▼
[FastAPI Service — ClusterIP]
   │
   ├──▶ [Model Inference Workers]
   │
   └──▶ [Audit Log Sink — write-only]
              │
              ▼
        [CloudWatch / ELK]
```

- All inter-service communication within cluster over mTLS
- Secrets injected via Vault / Secrets Manager — never in environment variables or image layers
- RBAC enforced at Kubernetes namespace level
- Image signing enforced on all promoted container images

---

## 8. CI/CD Pipeline Architecture

```
Developer Push / PR
        │
        ▼
┌──────────────────────────────────┐
│  GitHub Actions CI Workflow      │
│                                  │
│  1. Linting (ruff)               │
│  2. Type checking (mypy)         │
│  3. Unit tests (pytest)          │
│  4. Integration tests            │
│  5. API contract tests           │
│  6. Model threshold check        │
│  7. Container build              │
│  8. Dependency vulnerability scan│
│  9. Secret scan (gitleaks)       │
│  10. Infrastructure lint (helm)  │
└──────────────────────────────────┘
        │
        ▼ (all gates pass)
  Merge to main ──▶ Deploy to Test
        │
        ▼ (release tag)
  Deploy to Staging ──▶ UAT + Load Test
        │
        ▼ (Go/No-Go approval)
  Deploy to Production (Blue-Green)
```

---

## 9. NFR Compliance Mapping

| NFR | Architecture Decision |
|---|---|
| p95 latency < 800 ms | EfficientNet-B4 fallback; async preprocessing; GPU inference workers |
| ≥ 99.5% uptime | Kubernetes HPA + liveness/readiness probes; blue-green deployment |
| APCER/AuDET targets | Ensemble of three diverse backbones; threshold tuning on validation |
| TLS everywhere | NGINX ingress terminates TLS; mTLS between internal services |
| No secrets in code | Vault / Secrets Manager; pre-commit secret scanner |
| ≥ 80% test coverage | pytest-cov gate in CI pipeline |
| EU AI Act logging | Structured audit log on every inference; immutable write-only sink |

---

## 10. Key Architecture Decisions Index

Full records in [adr/](adr/). Summary:

| ADR | Decision |
|---|---|
| ADR-001 | PyTorch + timm selected as ML framework |
| ADR-002 | FastAPI selected as inference API framework |
| ADR-003 | MLflow selected for experiment tracking and model registry |
| ADR-004 | DVC selected for dataset versioning |
| ADR-005 | Hydra selected for configuration management |
| ADR-006 | Kubernetes selected as container orchestration platform |
| ADR-007 | GitHub Actions selected as CI/CD platform |
| ADR-008 | Blue-green deployment selected as release strategy |

---

## 11. Open Architecture Issues

| ID | Issue | Owner | Target Resolution |
|---|---|---|---|
| OA-01 | Confirm EVA-02-Large p95 latency on target GPU; determine if fallback weight adjustment is needed | Lead Data Scientist | Phase 3 Sprint 1 |
| OA-02 | Confirm Kubernetes hosting provider and cluster sizing | Infrastructure Lead | Phase 2 completion |
| OA-03 | Confirm whether MLflow will be self-hosted or managed | MLOps Engineer | Phase 2 completion |
| OA-04 | Confirm mTLS tooling — Istio vs. Linkerd vs. cloud-native | Infrastructure Lead | Phase 2 completion |

---

## 12. Sign-Off

| Name | Role | Signature | Date |
|---|---|---|---|
| Praveen Mittal | AI Solution Architect | | |
| [Name] | ARB Chair | | |
| [Name] | Security Lead | | |
| [Name] | Infrastructure Lead | | |
