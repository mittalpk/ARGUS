# ARGUS: Business Requirements Document (BRD)
## Document Control

| Field | Detail |
|---|---|
| **Document ID** | 02_BRD |
| **Version** | 1.0 |
| **Status** | Draft |
| **Author** | Praveen Mittal |
| **Reviewer** | Project Manager, Compliance Lead |
| **Date Created** | 2026-06-30 |
| **Last Updated** | 2026-06-30 |
| **Related Docs** | [00_Project_Charter.md](../Phase-0/00_Project_Charter.md), [01_Architecture_Vision.md](../Phase-0/01_Architecture_Vision.md) |

---

## 1. Executive Summary

Project ARGUS is a production-grade AI system designed to detect identity document fraud across three attack vectors: physical manipulations, GenAI-driven digital edits, and print-and-capture recapture attacks. This BRD captures the full set of functional, non-functional, compliance, and operational requirements that the ARGUS system must satisfy to be accepted for competition submission and production deployment.

---

## 2. Business Objectives

| ID | Objective | Priority |
|---|---|---|
| BO-01 | Achieve a competitive score on the FREUID Challenge 2026 leaderboard | Must Have |
| BO-02 | Detect all three fraud attack types with production-grade reliability | Must Have |
| BO-03 | Deliver a reusable, modular ML and inference architecture | Must Have |
| BO-04 | Comply with EU AI Act (High-Risk), GDPR, and ISO/IEC 42001 | Must Have |
| BO-05 | Provide explainable, auditable classification decisions | Should Have |
| BO-06 | Operate at production inference latency within defined SLO | Should Have |
| BO-07 | Support continuous retraining as fraud patterns evolve | Could Have |

---

## 3. Stakeholders

| Stakeholder | Role | Interest |
|---|---|---|
| Praveen Mittal | AI Solution Architect / Project Lead | System accuracy, architecture quality |
| Business Sponsor | Executive owner | Competition outcome, business value |
| Project Manager | Delivery governance | Schedule, risk, compliance |
| Lead Data Scientist | Model development | APCER/AuDET performance, model quality |
| MLOps Engineer | Pipeline and deployment | Reproducibility, CI/CD, monitoring |
| Security Lead | Security controls | Threat model, data protection |
| Compliance Lead | Regulatory adherence | EU AI Act, GDPR, ISO/IEC 42001 |
| Operations Lead | Production support | Uptime, alerting, incident response |

---

## 4. Functional Requirements

### 4.1 Core Detection

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-01 | The system SHALL classify an input document image as genuine or fraudulent | Must Have | BO-01, BO-02 |
| FR-02 | The system SHALL detect physical manipulation attack type on identity documents | Must Have | BO-02 |
| FR-03 | The system SHALL detect GenAI-driven digital editing attack type on identity documents | Must Have | BO-02 |
| FR-04 | The system SHALL detect print-and-capture (recapture) attack type | Must Have | BO-02 |
| FR-05 | The system SHALL return a fraud probability score between 0.0 and 1.0 | Must Have | BO-05 |
| FR-06 | The system SHALL return a confidence score alongside each classification | Should Have | BO-05 |
| FR-07 | The system SHALL return an attention/saliency map indicating the spatial region contributing to the decision | Should Have | BO-05 |
| FR-08 | The system SHALL flag low-confidence predictions for human review | Must Have | BO-05 |

### 4.2 API and Integration

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-09 | The system SHALL expose a REST API endpoint accepting a document image (JPEG/PNG, max 10 MB) | Must Have | BO-03 |
| FR-10 | The API SHALL return a structured JSON response with classification result, score, confidence, and request ID | Must Have | BO-03 |
| FR-11 | The API SHALL validate input schema and return a structured error response for invalid requests | Must Have | BO-03 |
| FR-12 | The API SHALL support batch inference of up to 32 documents per request | Should Have | BO-06 |
| FR-13 | The API SHALL provide a `/health` and `/ready` endpoint for infrastructure probes | Must Have | BO-03 |
| FR-14 | The API SHALL expose OpenAPI documentation at `/docs` | Should Have | BO-03 |

### 4.3 Data Pipeline

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-15 | The pipeline SHALL ingest images from the FREUID 2026 competition dataset | Must Have | BO-01 |
| FR-16 | The pipeline SHALL strip EXIF metadata from all images at ingestion | Must Have | BO-04 |
| FR-17 | The pipeline SHALL apply deterministic train/validation/test splits | Must Have | BO-01 |
| FR-18 | The pipeline SHALL apply configurable data augmentation during training | Must Have | BO-01 |
| FR-19 | The pipeline SHALL version datasets and preprocessing configurations | Must Have | BO-03 |

### 4.4 MLOps and Model Lifecycle

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-20 | Every training run SHALL log hyperparameters, metrics, and artifacts to the experiment tracker | Must Have | BO-03 |
| FR-21 | Trained models SHALL be registered in the model registry with version, dataset version, and git commit hash | Must Have | BO-03 |
| FR-22 | The system SHALL support champion-challenger model evaluation before production promotion | Must Have | BO-03 |
| FR-23 | The CI/CD pipeline SHALL enforce all defined quality gates before any environment promotion | Must Have | BO-03 |
| FR-24 | The system SHALL support automated rollback to the previous champion model | Must Have | BO-06 |

### 4.5 Monitoring

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-25 | The system SHALL monitor API latency, error rate, and throughput in production | Must Have | BO-06 |
| FR-26 | The system SHALL monitor model prediction distribution for drift | Should Have | BO-07 |
| FR-27 | The system SHALL trigger alerts when defined thresholds are breached | Must Have | BO-06 |
| FR-28 | The system SHALL retain structured logs of all inference requests for audit | Must Have | BO-04 |

---

## 5. Non-Functional Requirements

### 5.1 Performance

| ID | Requirement | Target | Priority |
|---|---|---|---|
| NFR-01 | Inference latency (single document, p95) | < 800 ms | Must Have |
| NFR-02 | API throughput | ≥ 100 requests/min | Must Have |
| NFR-03 | Training pipeline end-to-end runtime | < 24 hours on approved GPU | Should Have |
| NFR-04 | Model validation pipeline runtime | < 2 hours | Should Have |

### 5.2 Accuracy

| ID | Requirement | Target | Priority |
|---|---|---|---|
| NFR-05 | APCER at 1% BPCER | Minimise (competition target) | Must Have |
| NFR-06 | AuDET score | Maximise (competition target) | Must Have |
| NFR-07 | Ensemble model F1 on held-out validation set | ≥ 0.90 | Should Have |

### 5.3 Availability and Reliability

| ID | Requirement | Target | Priority |
|---|---|---|---|
| NFR-08 | Production API uptime | ≥ 99.5% | Must Have |
| NFR-09 | Recovery time objective (RTO) after incident | < 4 hours (Sev 1) | Must Have |
| NFR-10 | Recovery point objective (RPO) for model artifact | Zero — registry always maintained | Must Have |

### 5.4 Security

| ID | Requirement | Priority |
|---|---|---|
| NFR-11 | All API endpoints SHALL enforce TLS 1.2 or higher | Must Have |
| NFR-12 | Secrets SHALL NOT be stored in source code or container images | Must Have |
| NFR-13 | Container images SHALL be scanned for critical vulnerabilities before promotion | Must Have |
| NFR-14 | Access to model registry and training data SHALL be RBAC-controlled | Must Have |

### 5.5 Maintainability

| ID | Requirement | Priority |
|---|---|---|
| NFR-15 | Code coverage SHALL be ≥ 80% for core src modules | Should Have |
| NFR-16 | All public functions SHALL have type annotations | Should Have |
| NFR-17 | Dependency versions SHALL be pinned in requirements files | Must Have |
| NFR-18 | Every production model SHALL have an associated model card | Must Have |

---

## 6. Compliance Requirements

| ID | Regulation | Requirement | Owner |
|---|---|---|---|
| CR-01 | EU AI Act | ARGUS classified as High-Risk AI — requires risk management system, technical documentation, human oversight mechanism, and accuracy/robustness controls | Compliance Lead |
| CR-02 | EU AI Act | Transparency: end users must be informed they are interacting with an AI system | Compliance Lead |
| CR-03 | EU AI Act | Logging: all decisions must be logged for post-market monitoring | MLOps Engineer |
| CR-04 | GDPR | No PII retained beyond the duration of a single inference request | Security Lead |
| CR-05 | GDPR | EXIF and metadata stripped from images at ingestion | Data Engineer |
| CR-06 | GDPR | Data processing lawfulness documented | Compliance Lead |
| CR-07 | ISO/IEC 42001 | AI management system controls documented and implemented | Compliance Lead |
| CR-08 | ISO/IEC 42001 | Risk assessment and treatment plan maintained | AI Solution Architect |

---

## 7. Assumptions

| ID | Assumption |
|---|---|
| A-01 | The FREUID 2026 dataset is accessible via Kaggle API before Phase 3 begins |
| A-02 | Pre-trained weights for EVA-02-Large, ConvNeXt-V2-Base, and EfficientNet-B4 are publicly available |
| A-03 | The competition evaluation uses APCER @ 1% BPCER and AuDET as primary metrics |
| A-04 | The API will receive single-document requests in standard image formats (JPEG, PNG) |
| A-05 | GPU compute will be provisioned and available before Phase 3 model training begins |

---

## 8. Constraints

| ID | Constraint |
|---|---|
| C-01 | All training data must come from the approved FREUID 2026 competition dataset only |
| C-02 | Competition submission must be completed before the FREUID 2026 deadline |
| C-03 | GPU compute spend must remain within approved project budget |
| C-04 | System must be deployable as a container on Kubernetes |

---

## 9. Requirement Traceability Matrix

| Requirement ID | Business Objective | Phase | Document |
|---|---|---|---|
| FR-01 to FR-08 | BO-01, BO-02, BO-05 | Phase 3 | SAD, ML Design |
| FR-09 to FR-14 | BO-03, BO-06 | Phase 3 | SAD |
| FR-15 to FR-19 | BO-01, BO-03 | Phase 3 | DAD |
| FR-20 to FR-24 | BO-03 | Phase 3 | SAD, ML Design |
| FR-25 to FR-28 | BO-04, BO-06, BO-07 | Phase 4, 5 | Operations Runbook |
| NFR-01 to NFR-04 | BO-06 | Phase 3, 4 | SAD, Test Strategy |
| NFR-05 to NFR-07 | BO-01, BO-02 | Phase 3 | ML Design, Test Strategy |
| NFR-08 to NFR-10 | BO-06 | Phase 4, 5 | Operations Runbook |
| NFR-11 to NFR-14 | BO-04 | Phase 2, 4 | SAD, Security Compliance |
| CR-01 to CR-08 | BO-04 | Phase 2, 4 | Security Compliance |

---

## 10. Sign-Off

| Praveen Mittal | AI Solution Architect | Approved | 2026-06-30 |
| Project Manager | Project Manager | Approved | 2026-06-30 |
| Business Sponsor | Business Sponsor | Approved | 2026-06-30 |
| Compliance Lead | Compliance Lead | Approved | 2026-06-30 |
