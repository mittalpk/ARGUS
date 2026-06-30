# ARGUS: Use Case Specification
## Document Control

| Field | Detail |
|---|---|
| **Document ID** | 03_Use_Case_Specification |
| **Version** | 1.0 |
| **Status** | Draft |
| **Author** | Praveen Mittal |
| **Reviewer** | Project Manager, Lead Data Scientist |
| **Date Created** | 2026-06-30 |
| **Last Updated** | 2026-06-30 |
| **Related Docs** | [02_BRD.md](02_BRD.md), [01_Architecture_Vision.md](../Phase-0/01_Architecture_Vision.md) |

---

## 1. Overview

This document defines all use cases, user stories, failure modes, and edge cases for Project ARGUS. It serves as the primary input to the solution architecture (SAD), ML design (ML Design Doc), and test strategy documents.

---

## 2. Actors

| Actor | Description |
|---|---|
| **API Consumer** | Any system or service submitting a document image to the ARGUS REST API for classification |
| **ML Engineer** | Team member who trains, evaluates, and promotes models |
| **Data Engineer** | Team member who ingests, preprocesses, and versions datasets |
| **MLOps Engineer** | Team member who manages CI/CD, deployment, monitoring, and rollback |
| **Operations Lead** | Responsible for production uptime, incident response, and on-call |
| **Compliance Auditor** | External or internal reviewer assessing regulatory compliance evidence |
| **Human Reviewer** | Analyst who reviews low-confidence or flagged predictions |

---

## 3. Use Cases

---

### UC-01: Classify a Document Image as Genuine or Fraudulent

**Actor**: API Consumer
**Goal**: Determine whether a submitted document image is genuine or fraudulent
**Trigger**: API Consumer submits a POST request to `/classify` with a document image

**Preconditions**:
- ARGUS inference service is running and healthy
- Input image is a valid JPEG or PNG, ≤ 10 MB

**Main Flow**:
1. API Consumer sends POST `/classify` with image payload
2. API validates input format and size
3. Image is preprocessed: resize, normalise, EXIF strip
4. Preprocessed image is passed to the ensemble model
5. Each backbone produces a probability score
6. Ensemble aggregator produces a final fraud probability
7. API returns JSON response with: `result` (genuine/fraud), `fraud_score` (0.0–1.0), `confidence`, `request_id`, `latency_ms`

**Postconditions**:
- Request logged to audit log
- Response returned within p95 latency SLO (< 800 ms)

**Alternative Flows**:
- **A1** — Input image exceeds 10 MB: return HTTP 413 with error code `IMAGE_TOO_LARGE`
- **A2** — Input is not a valid image format: return HTTP 422 with error code `INVALID_IMAGE_FORMAT`
- **A3** — Confidence below threshold: result returned with `requires_human_review: true` flag

**Failure Modes**:

| Failure | Trigger | System Response |
|---|---|---|
| Model inference timeout | Backbone exceeds internal timeout | Return HTTP 503 with `INFERENCE_TIMEOUT` |
| OOM error on inference worker | Oversized image batch | Return HTTP 503; alert operations team |
| Corrupt image payload | Binary corruption in upload | Return HTTP 422 with `CORRUPT_IMAGE` |
| Dependency service unavailable | Model registry or feature store down | Return HTTP 503; trigger Sev 2 alert |

---

### UC-02: Detect Physical Manipulation Attack

**Actor**: API Consumer
**Goal**: Correctly identify a document that has been physically tampered with (scratching, laminate removal, photo substitution, ink alteration)

**Key Characteristics**:
- Attack leaves texture discontinuities and surface anomalies
- High-capacity backbones (EVA-02-Large, ConvNeXt-V2-Base) are primary contributors

**Expected Behaviour**:
- `fraud_score` > 0.80 for confirmed physical manipulation samples
- Attention map highlights manipulated region

**Edge Cases**:

| Case | Expected Behaviour |
|---|---|
| Document has natural wear and aging | Should score below fraud threshold; model must distinguish wear from manipulation |
| High-resolution scan vs. low-quality photograph | Model must generalise across input quality |
| Manipulation covers small area (< 5% of image) | Model must remain sensitive to localised changes |

---

### UC-03: Detect GenAI-Driven Digital Edit Attack

**Actor**: API Consumer
**Goal**: Identify documents where fields (name, date, photo) have been digitally altered using generative AI tools

**Key Characteristics**:
- Attack may produce near-perfect visual fidelity
- Detectable via frequency-domain artifacts, compression inconsistencies, and semantic anomalies

**Expected Behaviour**:
- `fraud_score` > 0.80 for confirmed GenAI-edited samples
- Saliency map indicates altered region

**Edge Cases**:

| Case | Expected Behaviour |
|---|---|
| Only a single character altered | Model must remain sensitive to minor semantic changes |
| Edited region compressed and re-saved multiple times | Model must not be fooled by compression laundering |
| GenAI tool produces no visible artifacts | Flag as low-confidence and require human review |

---

### UC-04: Detect Print-and-Capture (Recapture) Attack

**Actor**: API Consumer
**Goal**: Identify documents that have been digitally manipulated, printed, and re-photographed to mask digital editing traces

**Key Characteristics**:
- Attack introduces print rasterisation, Moiré patterns, and re-capture noise
- Can defeat frequency-domain detectors designed for direct digital edits

**Expected Behaviour**:
- `fraud_score` > 0.80 for confirmed recapture samples
- Model generalises across different print quality, lighting, and camera conditions

**Edge Cases**:

| Case | Expected Behaviour |
|---|---|
| High-quality laser print with professional scanner | Model must not classify as genuine due to high print quality |
| Document photographed under poor lighting | Model must not degrade significantly on lighting variation |
| Recaptured document with original document also partially visible | System processes the primary document region only |

---

### UC-05: Batch Inference Request

**Actor**: API Consumer
**Goal**: Submit multiple document images in a single API call for efficient classification

**Preconditions**:
- Batch size ≤ 32 images
- Each image individually valid per UC-01 constraints

**Main Flow**:
1. API Consumer sends POST `/classify/batch` with array of images
2. Each image validated and preprocessed independently
3. Batch passed through inference pipeline
4. Response returned as array matching input order

**Failure Modes**:
- If one image in batch is invalid, return partial response: valid results returned, failed images included with error codes
- If batch exceeds 32 images, return HTTP 422 with `BATCH_SIZE_EXCEEDED`

---

### UC-06: Train and Register a New Model

**Actor**: ML Engineer
**Goal**: Train a new candidate model, evaluate it, and register it in the model registry for review

**Main Flow**:
1. ML Engineer selects configuration via Hydra config file
2. Training script launched: `python src/training/train.py --config-name <name>`
3. Training run logs metrics, hyperparameters, and artifacts to MLflow
4. Evaluation script generates APCER, AuDET, F1, confusion matrix on validation set
5. Model artifact packaged and registered in MLflow Model Registry with full metadata
6. ML Engineer opens model governance review for champion-challenger evaluation

**Postconditions**:
- Run fully reproducible from logged config and dataset version
- Artifacts available for deployment pipeline

**Failure Modes**:

| Failure | Response |
|---|---|
| CUDA OOM during training | Reduce batch size in config; resume from last checkpoint |
| Dataset version mismatch | Pipeline halts; engineer resolves version conflict before restarting |
| Metric below minimum threshold | Model registered with `FAILED_VALIDATION` status; not eligible for production |

---

### UC-07: Deploy a New Champion Model

**Actor**: MLOps Engineer
**Goal**: Promote a validated candidate model to production using the blue-green deployment process

**Preconditions**:
- Model registered in registry with `APPROVED` status from governance review
- All CI/CD gates passing on release candidate

**Main Flow**:
1. MLOps Engineer triggers release pipeline from approved git tag
2. New container image built, scanned, and signed
3. Green environment deployed with new model
4. Smoke tests and health probes run automatically
5. Canary traffic routing begins at 5%
6. MLOps Engineer monitors latency, error rate, and prediction distribution
7. Traffic increased in increments: 5% → 25% → 50% → 100%
8. Blue environment decommissioned after release closure window

**Rollback Trigger**:
- Any rollback trigger condition in the runbook (Sev 1, latency >2x, error rate >5%) causes immediate traffic revert to blue

---

### UC-08: Trigger Human Review

**Actor**: ARGUS System → Human Reviewer
**Goal**: Route low-confidence predictions to a human analyst for manual adjudication

**Trigger**:
- `confidence` score below configured threshold (default: 0.70)
- Fraud score in ambiguous zone: 0.40 – 0.60

**Main Flow**:
1. Prediction returned with `requires_human_review: true`
2. Request logged with full metadata to human review queue
3. Human Reviewer accesses queue, reviews image, confidence, saliency map
4. Human Reviewer records final determination: genuine, fraudulent, or inconclusive
5. Determination logged for audit and model feedback

---

### UC-09: Monitor and Detect Model Drift

**Actor**: MLOps Engineer / Operations Lead
**Goal**: Detect when model prediction distribution or input data distribution has shifted from baseline

**Main Flow**:
1. Drift detection job runs on scheduled cadence (daily)
2. Compares current prediction distribution against baseline established at release
3. If drift score exceeds threshold for 3 consecutive windows, alert is raised
4. MLOps Engineer reviews alert, assesses cause, decides whether to trigger retraining

**Retraining Triggers** (per runbook):
- Drift threshold exceeded for 3 consecutive windows
- False positives increase >15% over baseline for 7 days
- False negatives increase >10% over baseline for 7 days

---

### UC-10: Compliance Audit Evidence Review

**Actor**: Compliance Auditor
**Goal**: Verify that ARGUS meets EU AI Act, GDPR, and ISO/IEC 42001 requirements

**Main Flow**:
1. Auditor requests access to compliance evidence pack
2. Security Lead provides controlled access to: inference logs, model cards, risk assessments, data processing records, incident logs
3. Auditor reviews controls against regulatory checklist
4. Findings documented; corrective actions tracked to closure

**Evidence Required**:
- Inference audit logs
- Model cards for each production model
- Risk management log
- Data processing records (EXIF stripping, retention policy)
- Incident log
- Change and release log

---

## 4. User Stories — Prioritised Backlog Seed

### Must Have (Phase 3 Sprint 1–2)

| ID | Story | Acceptance Criteria |
|---|---|---|
| US-01 | As a data engineer, I want to ingest the FREUID dataset and verify its integrity so training can begin | Dataset downloaded, schema validated, EXIF stripped, deterministic splits created |
| US-02 | As an ML engineer, I want to train a baseline EfficientNet-B4 model so we have an initial performance benchmark | Training completes without error; APCER, AuDET, F1 logged to MLflow |
| US-03 | As an ML engineer, I want to train EVA-02-Large and ConvNeXt-V2-Base so I can compare backbones | Both models trained; metrics compared in MLflow; no regressions vs. baseline |
| US-04 | As an MLOps engineer, I want a CI pipeline that runs linting, tests, and model checks on every PR | All gates run automatically; PRs blocked if any gate fails |

### Must Have (Phase 3 Sprint 3–4)

| ID | Story | Acceptance Criteria |
|---|---|---|
| US-05 | As an ML engineer, I want an ensemble model combining all three backbones so accuracy is maximised | Ensemble outperforms best individual backbone on APCER @ 1% BPCER |
| US-06 | As a developer, I want a FastAPI inference endpoint so the model can be called over HTTP | POST `/classify` accepts image, returns JSON with result, score, confidence, request_id |
| US-07 | As a developer, I want the API packaged as a Docker container so it can be deployed consistently | Container builds, passes scan, starts, and serves `/health` and `/classify` correctly |
| US-08 | As an ML engineer, I want confidence scores and attention maps returned so low-confidence cases can be reviewed | Every response includes `confidence` and `attention_map` URL or base64 |

### Should Have (Phase 3 Sprint 5)

| ID | Story | Acceptance Criteria |
|---|---|---|
| US-09 | As an MLOps engineer, I want a model registry so I can track and promote model versions | Models registered in MLflow with status lifecycle: staging → approved → production |
| US-10 | As an operations lead, I want Prometheus metrics and a Grafana dashboard so I can monitor the API in production | Dashboard shows p95 latency, error rate, throughput, and fraud score distribution |
| US-11 | As a compliance lead, I want structured inference audit logs so I can satisfy EU AI Act logging requirements | Every request logged with request_id, timestamp, result, score, model version |

### Could Have (Phase 5)

| ID | Story | Acceptance Criteria |
|---|---|---|
| US-12 | As an MLOps engineer, I want automated drift detection so model degradation is caught early | Daily drift job runs; alert fired when threshold exceeded |
| US-13 | As an ML engineer, I want an automated retraining trigger so the champion model stays current | Retraining pipeline launches automatically when drift or performance criteria met |

---

## 5. Failure Mode and Effects Summary

| Failure Mode | Attack Vector | Effect | Mitigation |
|---|---|---|---|
| Model misclassifies recapture as genuine | Recapture | Fraudulent document accepted | Dedicated recapture test set; recapture-specific augmentation |
| Model flags worn genuine document as fraud | Physical | Genuine document rejected | Hard negative mining with aged documents |
| API returns result after SLO breach | Any | Degraded user experience | EfficientNet-B4 fallback mode for latency budget |
| GenAI attack produces no detectable artifact | GenAI | Fraud escape | Flag as low-confidence; human review escalation |
| Training run not reproducible | MLOps | Model provenance broken | Enforce DVC + Hydra + seed locking |
| Compliance audit finds missing evidence | Audit | Regulatory risk | Compliance evidence checklist enforced at Phase 4 gate |

---

## 6. Sign-Off

| Name | Role | Signature | Date |
|---|---|---|---|
| Praveen Mittal | AI Solution Architect | | |
| [Name] | Project Manager | | |
| [Name] | Lead Data Scientist | | |
| [Name] | Compliance Lead | | |
