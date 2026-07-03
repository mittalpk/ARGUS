# ARGUS Initial Product Backlog
## Sprint 1 Seed Backlog

Source: `docs/03_Use_Case_Specification.md`

---

## Backlog Overview

This backlog is the initial delivery queue for Project ARGUS, seeded from the 14 user stories defined in the Use Case Specification. Sprint 1 prioritises data ingestion, validation, experiment tracking, baseline model training, and CI foundations.

### Prioritisation Key
- **P0** = Must do in Sprint 1
- **P1** = Should do soon after Sprint 1
- **P2** = Could do later / Phase 5+

---

## Sprint 1 Priority Items

| Rank | Story ID | Title | Priority | Owner | Estimate | Acceptance Summary |
|---|---|---|---|---|---:|---|
| 1 | US-01 | Ingest FREUID dataset and verify integrity | P0 | Data Engineer | 8 | Dataset downloaded, checksum validated, EXIF stripped, deterministic splits created |
| 2 | US-02 | Train EfficientNet-B4 baseline | P0 | Lead Data Scientist | 8 | Training completes; APCER, AuDET, F1 logged to MLflow |
| 3 | US-04 | CI pipeline for linting, tests, and model checks | P0 | MLOps Engineer | 8 | PRs blocked if any gate fails; automated checks running |
| 4 | US-03 | Train ConvNeXt-V2-Base and EVA-02-Large | P0 | Lead Data Scientist | 13 | Both models trained and compared against baseline in MLflow |
| 5 | US-09 | Model registry for version tracking and promotion | P1 | MLOps Engineer | 5 | Models registered with lifecycle states in MLflow |
| 6 | US-11 | Structured inference audit logs | P1 | Software Engineer | 5 | Every request logged with request_id, timestamp, result, score, model version |
| 7 | US-08 | Trigger human review for low-confidence predictions | P1 | Software Engineer | 5 | Responses include confidence, attention map, requires_human_review, and queue handoff |
| 8 | US-10 | Monitoring dashboard for production API | P1 | MLOps Engineer | 5 | Dashboard shows latency, error rate, throughput, fraud score distribution |
| 9 | US-06 | FastAPI inference endpoint | P1 | Software Engineer | 8 | POST /classify returns result, score, confidence, request_id |
| 10 | US-07 | Containerized deployment of API | P1 | MLOps Engineer | 5 | Container builds, scans, and serves health endpoints |
| 11 | US-05 | Ensemble model combining all three backbones | P1 | Lead Data Scientist | 13 | Ensemble outperforms best single backbone on APCER @ 1% BPCER |
| 12 | US-12 | Automated drift detection | P2 | MLOps Engineer | 3 | Daily drift job runs and alerts on threshold breach |
| 13 | US-13 | Automated retraining trigger | P2 | Lead Data Scientist | 5 | Retraining pipeline launches on drift/performance criteria |
| 14 | US-14 | Compliance evidence packaging | P1 | MLOps Engineer | 3 | Audit evidence pack can be generated on demand |

---

## Sprint 1 Breakdown

### Epic E-01: Data Foundation

| Story ID | Task | Owner | Dependency |
|---|---|---|---|
| US-01 | Download FREUID dataset via Kaggle API | Data Engineer | None |
| US-01 | Verify checksum and archive integrity | Data Engineer | Download complete |
| US-01 | Strip EXIF metadata from all images | Data Engineer | Validation passed |
| US-01 | Create deterministic train/val/test splits | Data Engineer | Clean dataset available |
| US-01 | Publish dataset version hash to DVC | MLOps Engineer | Split complete |

### Epic E-02: Baseline ML

| Story ID | Task | Owner | Dependency |
|---|---|---|---|
| US-02 | Implement EfficientNet-B4 training config | Lead Data Scientist | Data pipeline ready |
| US-02 | Train baseline model and log metrics | Lead Data Scientist | Config complete |
| US-02 | Generate confusion matrix and ROC/DET plots | Lead Data Scientist | Training complete |
| US-02 | Register baseline model in MLflow | MLOps Engineer | Metrics available |

### Epic E-03: Engineering Quality Gates

| Story ID | Task | Owner | Dependency |
|---|---|---|---|
| US-04 | Set up linting and formatting gates | MLOps Engineer | Repo structure in place |
| US-04 | Add unit test framework and sample tests | Software Engineer | Repo structure in place |
| US-04 | Add model threshold validation gate | MLOps Engineer | Baseline metrics available |
| US-04 | Add PR blocking in GitHub Actions | MLOps Engineer | CI jobs defined |

---

## Backlog by Story

### US-01: Ingest FREUID dataset and verify integrity
**Priority**: P0  
**Owner**: Data Engineer  
**Estimate**: 8 points

**Description**:
As a Data Engineer, I want to ingest, validate, and split the raw FREUID competition dataset, so that we strip all sensitive EXIF metadata to ensure GDPR compliance and generate deterministic splits for model benchmarking.

**Tasks**:
- Verify system has at least 60 GB free local disk space.
- Download competition dataset using kagglehub.
- Verify labels schema contains 'id'/'image_id' and 'label' columns.
- Strip EXIF metadata and handle various image modes (RGBA, RGB, P).
- Create stratified splits (70/15/15) using random seed 42.
- Track dataset splits using DVC (`data/splits.dvc`).

**Acceptance Criteria**:
- Ingestion machine has verified disk space before running.
- 100% of images in processed splits have empty EXIF metadata (verified via PIL `getexif()`).
- Ingestion fails gracefully and logs errors for zero-byte or unreadable image files.
- Train/validation/test splits are strictly disjoint (0% overlap) and stratified (maintaining target labels ratio).
- Dataset splits partition ratio is exactly 70% Train, 15% Validation, 15% Test using random seed 42.
- Data splits folder is registered in DVC.

---

### US-02: Train EfficientNet-B4 baseline
**Priority**: P0  
**Owner**: Lead Data Scientist  
**Estimate**: 8 points

**Description**:
As a Lead Data Scientist, I want to train a baseline EfficientNet-B4 model using Hydra configs and MLflow, so that we establish a reproducible, tracked baseline performance benchmark for all future backbone experiments.

**Tasks**:
- Define training parameters and dataset paths using Hydra configs.
- Implement EfficientNet-B4 model wrapper (`src/models/baseline.py`).
- Implement metrics module for APCER @ 1% BPCER, AuDET, and F1.
- Run baseline training loop and log metrics to MLflow (`src/training/train.py`).
- Implement active CUDA compatibility verification with CPU fallback.
- Export model checkpoint (`best_model.pth`) and confusion matrix to MLflow.

**Acceptance Criteria**:
- Parameters (epochs, learning rate, seed) are loaded via Hydra configs.
- Every run logs loss, APCER @ 1% BPCER, AuDET, and F1-score to MLflow.
- Training exports the best checkpoint (`best_model.pth`) and a confusion matrix plot to MLflow.
- The script automatically falls back to CPU if a CUDA driver or kernel mismatch is detected.
- Training runs using the same dataset splits and Hydra seed yield identical metric results.

---

### US-03: Train ConvNeXt-V2-Base and EVA-02-Large
**Priority**: P0  
**Owner**: Lead Data Scientist  
**Estimate**: 13 points

**Tasks**:
- Create configs for each backbone.
- Train ConvNeXt-V2-Base.
- Train EVA-02-Large.
- Benchmark latency for both.
- Compare metrics to baseline.

**Acceptance Criteria**:
- Both models trained and logged.
- Comparative report produced.
- Latency and performance trade-offs documented.

---

### US-04: CI pipeline for linting, tests, and model checks
**Priority**: P0  
**Owner**: MLOps Engineer  
**Estimate**: 8 points

**Tasks**:
- Add ruff lint/format checks.
- Add pytest unit test job.
- Add model threshold gate.
- Add dependency and secret scanning.
- Block PRs on failure.

**Acceptance Criteria**:
- PR pipeline runs automatically.
- Failing checks block merge.
- Model gate validates baseline metrics.

---

### Remaining Stories

### US-05: Ensemble model combining all three backbones
**Priority**: P1  
**Owner**: Lead Data Scientist  
**Estimate**: 13 points

### US-06: FastAPI inference endpoint
**Priority**: P1  
**Owner**: Software Engineer  
**Estimate**: 8 points

### US-07: Containerized deployment of API
**Priority**: P1  
**Owner**: MLOps Engineer  
**Estimate**: 5 points

### US-08: Trigger human review for low-confidence predictions
**Priority**: P1  
**Owner**: Software Engineer  
**Estimate**: 5 points

**Tasks**:
- Implement threshold check logic on classification output.
- Add `confidence` and `attention_map` base64/URL to API response payload.
- Add `requires_human_review` boolean flag to API response.
- Configure queue handoff for low-confidence cases.

**Acceptance Criteria**:
- Predictions with confidence < 0.70 are flagged with `requires_human_review: true`.
- Response payload contains both `confidence` and `attention_map`.
- Low-confidence payloads are routed to temporary secure storage for human review.

### US-09: Model registry for version tracking and promotion
**Priority**: P1  
**Owner**: MLOps Engineer  
**Estimate**: 5 points

### US-10: Monitoring dashboard for production API
**Priority**: P1  
**Owner**: MLOps Engineer  
**Estimate**: 5 points

### US-11: Structured inference audit logs
**Priority**: P1  
**Owner**: Software Engineer  
**Estimate**: 5 points

### US-12: Automated drift detection
**Priority**: P2  
**Owner**: MLOps Engineer  
**Estimate**: 3 points

### US-13: Automated retraining trigger
**Priority**: P2  
**Owner**: Lead Data Scientist  
**Estimate**: 5 points

### US-14: Compliance evidence packaging
**Priority**: P1  
**Owner**: MLOps Engineer  
**Estimate**: 3 points

---

## Suggested Sprint 1 Scope

### Commit to Sprint 1
- US-01
- US-02
- US-04

### Stretch if capacity remains
- US-03 (start ConvNeXt-V2-Base first, defer EVA-02 if needed)
- US-09 (model registry scaffolding)

### Defer until Sprint 2+
- US-05 through US-13 except support tasks needed for Sprint 1

---

## Definition of Ready
A backlog item enters a sprint only if:
- Acceptance criteria are clear.
- Owner is assigned.
- Dependencies are identified.
- Test approach is known.
- Data or environment prerequisites are available.

## Definition of Done
A backlog item is done only if:
- Code is merged.
- Tests pass.
- Relevant docs are updated.
- Evidence is stored in the release folder or MLflow.
- Reviewer approves the change.
