# ARGUS: Test Strategy
## Document Control

| Field | Detail |
|---|---|
| **Document ID** | 07_Test_Strategy |
| **Version** | 1.0 |
| **Status** | Draft |
| **Author** | Praveen Mittal |
| **Reviewer** | Tech Lead, Lead Data Scientist, Security Lead |
| **Date Created** | 2026-07-01 |
| **Last Updated** | 2026-07-01 |
| **Related Docs** | [04_SAD.md](../Phase-2/04_SAD.md), [06_ML_Design.md](06_ML_Design.md), [02_BRD.md](../Phase-1/02_BRD.md) |

---

## 1. Purpose

This document defines the complete testing strategy for Project ARGUS — covering all test types, acceptance criteria, tools, automation gates, and evidence requirements across the full project lifecycle. It is the authoritative reference for QA planning, CI/CD gate configuration, and release evidence packs.

---

## 2. Testing Objectives

| # | Objective |
|---|---|
| 1 | Verify every functional requirement in [02_BRD.md](../Phase-1/02_BRD.md) is implemented and working correctly |
| 2 | Validate every non-functional requirement (latency, throughput, availability) is met on target hardware |
| 3 | Confirm model accuracy meets APCER @ 1% BPCER and AuDET targets on the held-out test set |
| 4 | Validate security controls, input handling, and error responses are robust |
| 5 | Provide auditable evidence of all test outcomes for compliance and release governance |
| 6 | Enforce automated quality gates in CI/CD that block regressions from reaching production |

---

## 3. Test Scope

### In Scope

- Unit tests for all `src/` modules
- Integration tests for the full inference pipeline (image → API → result)
- API contract tests for all endpoints
- Model evaluation tests (accuracy metrics against defined thresholds)
- Performance and load tests for API and inference pipeline
- Security tests: dependency scanning, secret scanning, input fuzzing, container image scanning
- Data pipeline tests: schema validation, EXIF stripping, split determinism
- Rollback and blue-green deployment tests

### Out of Scope

- End-to-end UI testing (no frontend component)
- Browser compatibility testing
- Hardware-level stress testing beyond defined SLOs
- Penetration testing (covered by external security review in Phase 4)

---

## 4. Test Types and Levels

### 4.1 Unit Tests

**Purpose**: Verify individual functions and classes behave correctly in isolation.

**Scope**:

| Module | Key Test Areas |
|---|---|
| `src/data/ingestion.py` | EXIF-strip verification, schema validation, path-containment (`tests/unit/test_ingestion.py`) |
| `src/data/split.py` | Stratified split ratios, determinism with fixed seed (`tests/unit/test_split.py`) |
| `src/models/ensemble.py` | Forward pass output shape, weight normalisation, score range [0,1] (`tests/unit/test_ensemble.py`) |
| `src/models/baseline.py` | Shared backbone forward pass / feature extraction shape, parametrized over `eva02_large_patch14_448`, `convnextv2_base`, `efficientnet_b4` (`tests/unit/test_models.py`) |
| `src/training/train.py` | Seeding, DataLoader worker seeding, checkpoint save/load |
| `src/training/metrics.py` | APCER, BPCER, AuDET metric computation accuracy (`tests/unit/test_metrics.py`) |
| `src/api/main.py` | `/classify` input validation, response schema, error codes (`tests/unit/test_api.py`) |
| `src/api/retraining.py` | RBAC (role header + shared-secret API key), rate limiting (`tests/unit/test_retraining.py`) |

**Tooling**: `pytest`, `pytest-cov`
**Coverage Gate**: ≥ 80% line coverage across `src/`
**Location**: `tests/unit/`

**Example Tests**:
```python
# tests/unit/test_preprocess.py
def test_exif_strip_removes_all_metadata(sample_image_with_exif):
    result = strip_exif(sample_image_with_exif)
    assert get_exif_data(result) == {}

def test_resize_produces_correct_shape():
    img = torch.rand(3, 1024, 768)
    result = resize_for_backbone(img, backbone="efficientnet_b4")
    assert result.shape == (3, 380, 380)

def test_normalisation_values_within_range():
    img = torch.rand(3, 380, 380)
    result = normalise(img)
    assert result.min() >= -3.0 and result.max() <= 3.0

# tests/unit/test_ensemble.py
def test_fraud_score_in_unit_range(mock_ensemble, sample_batch):
    out = mock_ensemble(sample_batch)
    assert (out["fraud_score"] >= 0.0).all()
    assert (out["fraud_score"] <= 1.0).all()

def test_ensemble_weights_sum_to_one(mock_ensemble, sample_batch):
    out = mock_ensemble(sample_batch)
    assert torch.isclose(out["ensemble_weights"].sum(), torch.tensor(1.0))
```

---

### 4.2 Integration Tests

**Purpose**: Verify end-to-end behaviour across connected components — from image input through the full inference pipeline to API response.

**Key Scenarios**:

| Test ID | Scenario | Expected Result |
|---|---|---|
| IT-01 | Valid JPEG submitted to POST /classify | HTTP 200; valid JSON with all required fields |
| IT-02 | Valid PNG submitted to POST /classify | HTTP 200; valid JSON |
| IT-03 | Known fraudulent image submitted | fraud_score > 0.5 |
| IT-04 | Known genuine image submitted | fraud_score < 0.5 |
| IT-05 | Image > 10 MB submitted | HTTP 413, error code IMAGE_TOO_LARGE |
| IT-06 | Non-image file submitted | HTTP 422, error code INVALID_IMAGE_FORMAT |
| IT-07 | Corrupt binary submitted | HTTP 422, error code CORRUPT_IMAGE |
| IT-08 | Batch of 32 valid images | HTTP 200; array of 32 results in correct order |
| IT-09 | Batch of 33 images | HTTP 422, error code BATCH_SIZE_EXCEEDED |
| IT-10 | Batch with one invalid image | HTTP 200; partial response; invalid image has error code |
| IT-11 | GET /health when service running | HTTP 200 |
| IT-12 | GET /ready when model loaded | HTTP 200 |
| IT-13 | GET /ready before model loaded | HTTP 503 |
| IT-14 | Low-confidence image submitted | Response includes requires_human_review: true |
| IT-15 | All response fields present and typed correctly | Schema validation passes |

**Tooling**: `pytest`, `httpx` (async test client), `fastapi.testclient.TestClient`
**Location**: `tests/integration/`

---

### 4.3 API Contract Tests

**Purpose**: Verify the API conforms to the OpenAPI specification and all contracts defined in the SAD are enforced.

**Approach**: Use `schemathesis` to auto-generate test cases from the OpenAPI schema and fuzz all endpoints.

**Key Checks**:
- All documented endpoints exist and respond
- Request bodies with missing required fields return HTTP 422
- Response bodies conform to defined JSON schema
- Error codes match documented values
- Content-type headers are correct
- OpenAPI spec at `/docs` loads correctly

**Tooling**: `schemathesis`, `pytest`
**Location**: `tests/integration/test_api_contract.py`

---

### 4.4 Model Evaluation Tests

**Purpose**: Validate that trained model artifacts meet the defined accuracy thresholds before they are eligible for production promotion.

**Evaluation Gate** (runs in CI on model promotion step):

| Metric | Minimum Threshold | Fail Action |
|---|---|---|
| APCER @ 1% BPCER (validation) | Below competition baseline | Block promotion; log failure |
| AuDET (validation) | Better than EfficientNet-B4 baseline | Block promotion; log failure |
| F1-score (validation) | ≥ 0.90 | Block promotion; log failure |
| Calibration Error (ECE) | ≤ 0.05 | Warning; does not block |

**Test Data**: Validation set only. Test set is accessed exclusively during final pre-submission evaluation.

**Tooling**: `pytest`, custom `src/training/evaluate.py`, MLflow metric assertions
**Location**: `tests/unit/test_model_metrics.py`

```python
# tests/unit/test_model_metrics.py
def test_apcer_below_baseline(champion_model, val_dataloader, baseline_apcer):
    apcer = compute_apcer_at_bpcer(champion_model, val_dataloader, bpcer_target=0.01)
    assert apcer < baseline_apcer, f"APCER {apcer:.4f} not below baseline {baseline_apcer:.4f}"

def test_f1_above_threshold(champion_model, val_dataloader):
    f1 = compute_f1(champion_model, val_dataloader)
    assert f1 >= 0.90, f"F1 {f1:.4f} below threshold 0.90"
```

---

### 4.5 Performance Tests

**Purpose**: Verify the inference API meets latency and throughput SLOs under realistic and peak load conditions.

**Test Scenarios**:

| Test ID | Scenario | Pass Criteria |
|---|---|---|
| PT-01 | Single request latency — warm model | p50 < 400 ms; p95 < 800 ms; p99 < 1200 ms |
| PT-02 | Sustained load — 100 req/min for 10 min | No error rate increase; latency SLO maintained |
| PT-03 | Burst load — 300 req/min for 2 min | Graceful degradation; no crash; error rate < 1% |
| PT-04 | Batch of 32 images | Total response p95 < 5000 ms |
| PT-05 | Cold start — model load time | Model serving within 60 seconds of pod start |
| PT-06 | Memory footprint under sustained load | RSS < 80% of container memory limit |

**Tooling**: `locust`
**Location**: `tests/performance/`
**Environment**: Staging only (not dev or CI runner)

```python
# tests/performance/locustfile.py
from locust import HttpUser, task, between
import base64

class ARGUSUser(HttpUser):
    wait_time = between(0.2, 0.6)

    @task
    def classify_document(self):
        with open("tests/fixtures/sample_genuine.jpg", "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()
        self.client.post("/v1/classify", json={
            "image": image_b64,
            "image_format": "jpeg"
        })
```

---

### 4.6 Security Tests

**Purpose**: Validate that the system is hardened against known vulnerability classes and that all security controls defined in the SAD are functioning.

| Test Type | Tool | Gate | Frequency |
|---|---|---|---|
| Dependency vulnerability scan | `trivy` (filesystem) | Block on CRITICAL | Every PR + release |
| Container image scan | `trivy` (image) | Block on CRITICAL | Every image build |
| Secret scan | `gitleaks` | Block on any secret | Every commit |
| SAST (static analysis) | `bandit` | Block on HIGH severity | Every PR |
| Input fuzzing — API | `schemathesis` | No 500 errors on valid schema inputs | Every PR |
| EXIF strip verification | Custom pytest | All metadata removed | Every PR |
| RBAC validation | Manual + automated Kubernetes policy test | Least privilege confirmed | Per environment provisioning |

**Location**: `tests/` (automated); `.github/workflows/ci.yml` (CI gates)

---

### 4.7 Data Pipeline Tests

**Purpose**: Validate the data ingestion, preprocessing, and versioning pipeline is correct, deterministic, and compliant.

| Test ID | Test | Pass Criteria |
|---|---|---|
| DP-01 | Dataset download and checksum | Hash matches expected; no corruption |
| DP-02 | EXIF strip on all dataset images | Zero images with remaining EXIF after processing |
| DP-03 | Split determinism | Re-running split with same seed produces identical splits |
| DP-04 | Train/val/test split isolation | No image appears in more than one split |
| DP-05 | Label completeness | 100% of train/val images have a label |
| DP-06 | Class balance report | Report generated and logged |
| DP-07 | Corrupt image detection | Corrupt files flagged and excluded |
| DP-08 | Tensor shape correctness per backbone | All tensors have expected CHW dimensions |

**Location**: `tests/unit/test_data_pipeline.py`

---

### 4.8 Deployment and Rollback Tests

**Purpose**: Validate that deployment automation, health probes, and rollback procedures work correctly in a staging environment.

| Test ID | Test | Pass Criteria |
|---|---|---|
| DR-01 | Blue-green deploy to staging | Green environment serves traffic; blue retained |
| DR-02 | Health probe response | /health returns 200 within 30 seconds of pod start |
| DR-03 | Readiness probe response | /ready returns 200 only after model is loaded |
| DR-04 | Rollback execution | Traffic routes back to blue within 2 minutes of rollback trigger |
| DR-05 | Canary traffic split | 5% traffic routed to green correctly; confirmed via metrics |
| DR-06 | Old blue environment decommission | Blue pods terminated correctly after release closure |

**Environment**: Staging only
**Owner**: MLOps Engineer

---

## 5. Test Data Management

| Data Type | Source | Usage | Privacy |
|---|---|---|---|
| Unit test fixtures | Synthetic generated images | Unit and integration tests | No PII; synthetic only |
| Integration test fixtures | Small approved sample of FREUID data | IT-01 to IT-15 | No PII; EXIF stripped |
| Performance test fixtures | Synthetic images at target resolution | Load tests | Synthetic only |
| Model evaluation data | Validation split of FREUID dataset | Model gate tests | Access-controlled |
| Security fuzz inputs | Auto-generated by schemathesis | API contract tests | Synthetic |

All test fixtures committed to `tests/fixtures/` (small files only). Large datasets referenced via DVC and not committed to git.

---

## 6. Test Environments

| Environment | Test Types | Data | Automated |
|---|---|---|---|
| Local (dev) | Unit, integration (partial) | Synthetic fixtures | Manually triggered |
| CI (GitHub Actions) | Unit, integration, contract, security, model gate | Synthetic + validation split | On every PR and merge |
| Staging | Performance, deployment, rollback | Masked production-like data | On release candidate |
| Production | Smoke tests post-deploy | Live | On deployment completion |

---

## 7. CI/CD Test Gate Configuration

Gates run in order. Any failure blocks the pipeline at that stage.

```
PR Opened / Commit Pushed
          │
          ▼
┌─────────────────────────────────┐
│ Gate 1: Code Quality            │
│  - ruff lint                    │
│  - ruff format check            │
│  - mypy type checking           │
└─────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────┐
│ Gate 2: Unit Tests              │
│  - pytest tests/unit/           │
│  - Coverage ≥ 80%               │
└─────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────┐
│ Gate 3: Integration Tests       │
│  - pytest tests/integration/    │
│  - API contract (schemathesis)  │
└─────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────┐
│ Gate 4: Security                │
│  - gitleaks secret scan         │
│  - bandit SAST                  │
│  - trivy dependency scan        │
└─────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────┐
│ Gate 5: Container               │
│  - docker build                 │
│  - trivy image scan             │
│  - healthcheck probe            │
└─────────────────────────────────┘
          │
          ▼ (release candidate only)
┌─────────────────────────────────┐
│ Gate 6: Model Evaluation        │
│  - APCER @ 1% BPCER threshold   │
│  - F1 ≥ 0.90                    │
│  - AuDET improvement check      │
└─────────────────────────────────┘
          │
          ▼ (staging deployment)
┌─────────────────────────────────┐
│ Gate 7: Performance             │
│  - locust load test             │
│  - p95 latency < 800 ms         │
│  - Error rate < 1%              │
└─────────────────────────────────┘
```

---

## 8. Test Evidence Requirements

The following evidence must be archived in the release evidence pack before any production deployment:

| Evidence Item | Source | Required For |
|---|---|---|
| Unit test report (HTML) | pytest | Every release |
| Coverage report (HTML) | pytest-cov | Every release |
| Integration test report | pytest | Every release |
| API contract test report | schemathesis | Every release |
| Security scan reports | trivy, gitleaks, bandit | Every release |
| Model evaluation report | MLflow + pytest | Every release |
| Performance test report | locust HTML report | Every release |
| Deployment smoke test log | GitHub Actions | Every release |
| Rollback test evidence | Manual log | Phase 4 initial release |

All evidence stored in the release artefact store and referenced in the release notes.

---

## 9. Defect Management

| Severity | Definition | SLA to Fix |
|---|---|---|
| Critical | System crash, data loss, security breach, or fraud escape | Before release; block deployment |
| High | Feature broken, SLO breach, or test gate failure | Current sprint |
| Medium | Degraded behaviour, non-critical failure | Next sprint |
| Low | Minor issue, cosmetic, documentation | Planned backlog |

All defects tracked in the project management tool with severity, owner, and sprint assignment.

---

## 10. Definition of Test Complete

Phase 3 testing is complete when:

- [ ] All unit tests passing; coverage ≥ 80%
- [ ] All integration tests passing
- [ ] API contract tests passing with no 500 errors
- [ ] All security gates passing; no unresolved CRITICAL findings
- [ ] Model evaluation gate passing on validation set
- [ ] Performance test passing in staging (p95 < 800 ms, error rate < 1%)
- [ ] Deployment and rollback tests passing in staging
- [ ] All test evidence archived in release evidence pack
- [ ] No open Critical or High defects

---

## 11. Sign-Off

| Praveen Mittal | AI Solution Architect | Approved | 2026-07-02 |
| Tech Lead | Tech Lead | Approved | 2026-07-02 |
| Lead Data Scientist | Lead Data Scientist | Approved | 2026-07-02 |
| Security Lead | Security Lead | Approved | 2026-07-02 |
