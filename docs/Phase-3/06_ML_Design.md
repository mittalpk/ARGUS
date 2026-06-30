# ARGUS: ML Design Document
## Document Control

| Field | Detail |
|---|---|
| **Document ID** | 06_ML_Design |
| **Version** | 1.0 |
| **Status** | Draft |
| **Author** | Praveen Mittal |
| **Reviewer** | Lead Data Scientist, AI Solution Architect |
| **Date Created** | 2026-07-01 |
| **Last Updated** | 2026-07-01 |
| **Related Docs** | [04_SAD.md](../Phase-2/04_SAD.md), [05_DAD.md](../Phase-2/05_DAD.md), [02_BRD.md](../Phase-1/02_BRD.md) |

---

## 1. Purpose

This document defines the complete machine learning design for Project ARGUS — covering the problem formulation, model architecture, training strategy, loss functions, hyperparameter space, evaluation protocol, ensemble design, inference optimisation, and model governance. It serves as the authoritative specification for all ML development in Phase 3.

---

## 2. Problem Formulation

| Attribute | Definition |
|---|---|
| **Task** | Binary image classification — genuine (0) vs. fraudulent (1) |
| **Input** | Single RGB document image, variable resolution |
| **Output** | Fraud probability score ∈ [0.0, 1.0]; binary label at chosen threshold |
| **Attack Types** | Physical manipulation, GenAI digital edit, Print-and-capture recapture |
| **Primary Metric** | APCER @ 1% BPCER (Attack Presentation Classification Error Rate at 1% Bona Fide Presentation Classification Error Rate) |
| **Secondary Metric** | AuDET (Area under Detection Error Trade-off curve) |
| **Operational Metric** | F1-score ≥ 0.90 on held-out validation set |
| **Constraint** | p95 inference latency < 800 ms per document |

### Metric Definitions

**BPCER** = FP / (FP + TN) — rate at which genuine documents are incorrectly rejected.

**APCER** = FN / (FN + TP) — rate at which fraudulent documents are incorrectly accepted.

**APCER @ 1% BPCER** = APCER value when the operating threshold is set such that BPCER = 1%. Lower is better.

**AuDET** = Area under the Detection Error Trade-off curve (APCER vs. BPCER across all thresholds). Lower area is better; equivalent to minimising total classification error across all operating points.

---

## 3. Backbone Architectures

### 3.1 EVA-02-Large

| Attribute | Detail |
|---|---|
| Architecture | Vision Transformer (ViT-Large) with EVA pre-training |
| Pretrained On | ImageNet-21k + EVA CLIP |
| Input Resolution | 448 × 448 |
| Parameters | ~307M |
| Strengths | Highest capacity; captures long-range spatial dependencies; excellent for subtle texture and semantic anomalies |
| Weaknesses | Highest latency; highest memory footprint |
| Role in Ensemble | Primary accuracy contributor for GenAI and recapture attacks |
| timm Model ID | `eva02_large_patch14_448.mim_m38m_ft_in22k_in1k` |

### 3.2 ConvNeXt-V2-Base

| Attribute | Detail |
|---|---|
| Architecture | Pure convolutional; ConvNeXt-V2 with FCMAE pre-training |
| Pretrained On | ImageNet-22k |
| Input Resolution | 384 × 384 |
| Parameters | ~89M |
| Strengths | Strong local texture feature extraction; efficient for detecting physical manipulation artifacts |
| Weaknesses | Limited long-range dependency modelling |
| Role in Ensemble | Primary contributor for physical manipulation detection |
| timm Model ID | `convnextv2_base.fcmae_ft_in22k_in1k_384` |

### 3.3 EfficientNet-B4

| Attribute | Detail |
|---|---|
| Architecture | EfficientNet compound-scaled CNN |
| Pretrained On | ImageNet-1k |
| Input Resolution | 380 × 380 |
| Parameters | ~19M |
| Strengths | Lowest latency; lowest memory; strong baseline accuracy |
| Weaknesses | Lower capacity for subtle GenAI artifacts |
| Role in Ensemble | Latency fallback; strong baseline; recapture generalisation |
| timm Model ID | `efficientnet_b4.ra2_in1k` |

---

## 4. Model Architecture Design

### 4.1 Individual Backbone Wrapper

Each backbone is wrapped in a common `ARGUSBackbone` class:

```python
class ARGUSBackbone(nn.Module):
    def __init__(self, model_name: str, pretrained: bool = True, drop_rate: float = 0.2):
        super().__init__()
        self.encoder = timm.create_model(model_name, pretrained=pretrained,
                                          num_classes=0, drop_rate=drop_rate)
        self.head = nn.Sequential(
            nn.Linear(self.encoder.num_features, 512),
            nn.GELU(),
            nn.Dropout(drop_rate),
            nn.Linear(512, 1)
        )

    def forward(self, x: torch.Tensor) -> dict:
        features = self.encoder(x)
        logit = self.head(features).squeeze(1)
        return {"logit": logit, "features": features}
```

### 4.2 Ensemble Model

```python
class ARGUSEnsemble(nn.Module):
    def __init__(self, backbones: list[ARGUSBackbone]):
        super().__init__()
        self.backbones = nn.ModuleList(backbones)
        # Learnable per-backbone weights, softmax-normalised
        self.weights = nn.Parameter(torch.ones(len(backbones)))

    def forward(self, inputs: list[torch.Tensor]) -> dict:
        scores = torch.stack([
            torch.sigmoid(b(x)["logit"])
            for b, x in zip(self.backbones, inputs)
        ], dim=1)  # (B, num_backbones)
        w = torch.softmax(self.weights, dim=0)
        fraud_score = (scores * w).sum(dim=1)  # (B,)
        return {
            "fraud_score": fraud_score,
            "backbone_scores": scores,
            "ensemble_weights": w
        }
```

### 4.3 Attention / Saliency Map

GradCAM is applied to the highest-weighted backbone at inference time to produce the attention map returned by the API (FR-07). Implementation uses `pytorch-grad-cam` library targeting the final convolutional/attention layer of each backbone.

---

## 5. Training Strategy

### 5.1 Training Phases

| Phase | Description | Epochs | LR Strategy |
|---|---|---|---|
| **Phase A: Backbone Fine-tuning** | Train each backbone independently on ARGUS dataset with frozen early layers | 10 | Cosine annealing with warm-up |
| **Phase B: Full Fine-tuning** | Unfreeze all layers and fine-tune end-to-end | 20 | Cosine annealing, lower LR |
| **Phase C: Ensemble Weight Learning** | Freeze backbones; learn ensemble aggregation weights on validation set | 5 | Fixed low LR |

### 5.2 Layer Freezing Strategy

| Backbone | Frozen Layers (Phase A) | Unfrozen Layers (Phase A) |
|---|---|---|
| EVA-02-Large | Patch embedding + first 18 transformer blocks | Last 6 blocks + head |
| ConvNeXt-V2-Base | Stem + first 2 stages | Last 2 stages + head |
| EfficientNet-B4 | Stem + blocks 0–4 | Blocks 5–6 + head |

### 5.3 Optimiser Configuration

| Parameter | Phase A | Phase B | Phase C |
|---|---|---|---|
| Optimiser | AdamW | AdamW | Adam |
| Learning Rate | 1e-4 | 5e-5 | 1e-3 |
| Weight Decay | 1e-2 | 1e-2 | 0 |
| Gradient Clipping | 1.0 | 1.0 | — |
| Batch Size | 32 | 16 (EVA-02), 32 (others) | 64 |
| Mixed Precision | fp16 | fp16 | fp32 |

### 5.4 Learning Rate Schedule

```
Warm-up: linear ramp over first 5% of total steps
Decay:   cosine annealing from peak LR to 1e-6
Restart: none (single cosine cycle per phase)
```

### 5.5 Class Imbalance Handling

Strategy selected based on Phase 3 Sprint 1 EDA findings. Options in order of preference:

1. **Weighted random sampler** — oversample the minority class to achieve 1:1 ratio per batch
2. **Focal loss** — down-weight easy negatives; preferred if imbalance > 3:1
3. **Class-weighted BCE** — simple alternative if imbalance is mild (< 2:1)

---

## 6. Loss Functions

### 6.1 Primary Loss — Binary Cross-Entropy with Logits

$$
\mathcal{L}_{BCE} = -\frac{1}{N} \sum_{i=1}^{N} \left[ y_i \log \sigma(z_i) + (1 - y_i) \log (1 - \sigma(z_i)) \right]
$$

### 6.2 Focal Loss (if class imbalance > 3:1)

$$
\mathcal{L}_{FL} = -\frac{1}{N} \sum_{i=1}^{N} \alpha_t (1 - p_t)^{\gamma} \log(p_t)
$$

Default parameters: $\alpha = 0.25$, $\gamma = 2.0$.

### 6.3 Auxiliary Consistency Loss (optional — Phase B)

Penalises excessive divergence between backbone predictions to encourage ensemble coherence:

$$
\mathcal{L}_{cons} = \frac{1}{K(K-1)} \sum_{i \neq j} \text{KL}(p_i \| p_j)
$$

Total loss: $\mathcal{L} = \mathcal{L}_{BCE} + \lambda \mathcal{L}_{cons}$, where $\lambda = 0.1$.

---

## 7. Hyperparameter Space

### 7.1 Baseline Hyperparameters

| Hyperparameter | Baseline Value | Search Range |
|---|---|---|
| Learning Rate (Phase A) | 1e-4 | [1e-5, 5e-4] |
| Learning Rate (Phase B) | 5e-5 | [1e-5, 1e-4] |
| Weight Decay | 1e-2 | [1e-3, 1e-1] |
| Dropout Rate | 0.2 | [0.1, 0.5] |
| Batch Size | 32 | [16, 64] |
| Warm-up Ratio | 0.05 | [0.02, 0.10] |
| Focal Loss gamma | 2.0 | [1.0, 5.0] |
| Consistency loss lambda | 0.1 | [0.0, 0.5] |
| Ensemble weight temperature | 1.0 (softmax) | [0.5, 2.0] |

### 7.2 Hyperparameter Search Strategy

| Phase | Method | Budget |
|---|---|---|
| Sprint 2 | Manual grid on key LR and dropout | 10–20 runs per backbone |
| Sprint 3 | Hydra multirun sweep (random search) | 30 runs total |
| Sprint 4 | Optuna Bayesian optimisation (if needed) | 50 runs |

All sweeps run on validation set APCER @ 1% BPCER. No test set access during search.

---

## 8. Evaluation Protocol

### 8.1 Metrics Computed Per Run

| Metric | Split | Threshold |
|---|---|---|
| APCER @ 1% BPCER | Validation | Derived from ROC |
| AuDET | Validation | — |
| AUROC | Validation | — |
| F1-score | Validation | 0.5 (default); optimal threshold |
| Precision / Recall | Validation | Optimal threshold |
| Confusion Matrix | Validation | Optimal threshold |
| Calibration Error (ECE) | Validation | — |
| Per-attack-type breakdown | Validation | Optimal threshold |

### 8.2 Threshold Selection

The operating threshold is set on the validation set to satisfy **BPCER = 1%**. This threshold is then fixed and applied to the test set and competition submission. It must not be re-tuned after test set evaluation.

### 8.3 Minimum Acceptance Criteria

A model is eligible for production promotion only if it meets **all** of the following on the validation set:

| Criterion | Threshold |
|---|---|
| APCER @ 1% BPCER | Below competition baseline |
| AuDET | Improvement over EfficientNet-B4 single-backbone baseline |
| F1-score | ≥ 0.90 |
| p95 Inference Latency | < 800 ms (measured on target GPU) |

### 8.4 Model Card Requirements

Every promoted model must include a model card documenting:

- model version and git commit
- dataset version and split hashes
- training configuration (Hydra config snapshot)
- validation metrics (all metrics in 8.1)
- inference latency on target hardware
- known failure modes and limitations
- compliance notes

---

## 9. Experiment Plan by Sprint

### Sprint 1 — Data and Baseline

| Task | Owner | Acceptance Criteria |
|---|---|---|
| Ingest and validate FREUID dataset | Data Engineer | Dataset downloaded, schema validated, EDA notebook complete |
| Confirm class balance and attack type distribution | Lead Data Scientist | Class balance report logged; imbalance strategy selected |
| Train EfficientNet-B4 baseline | Lead Data Scientist | Training completes; APCER, AuDET, F1 logged to MLflow |
| Establish MLflow and DVC pipeline | MLOps Engineer | Reproducible run: re-run produces identical metrics |

### Sprint 2 — Backbone Experiments

| Task | Owner | Acceptance Criteria |
|---|---|---|
| Fine-tune ConvNeXt-V2-Base | Lead Data Scientist | Metrics logged; comparison with EfficientNet-B4 baseline in MLflow |
| Fine-tune EVA-02-Large | Lead Data Scientist | Metrics logged; latency benchmarked on target GPU |
| Resolve OA-01 (EVA-02 latency) | Lead Data Scientist | Latency decision documented in ADR-001 update |
| Implement GradCAM saliency maps | ML Engineer | Attention map returned correctly for all three backbones |

### Sprint 3 — Ensemble and Optimisation

| Task | Owner | Acceptance Criteria |
|---|---|---|
| Train ensemble model (Phase C) | Lead Data Scientist | Ensemble outperforms best single backbone on APCER @ 1% BPCER |
| Hyperparameter sweep (Hydra multirun) | Lead Data Scientist | Best config identified and logged; improvement documented |
| API integration with ensemble | Software Engineer | POST /classify returns fraud_score, confidence, attention_map |
| CI model threshold gate | MLOps Engineer | CI fails if APCER @ 1% BPCER regresses beyond tolerance |

### Sprint 4 — Hardening and QA

| Task | Owner | Acceptance Criteria |
|---|---|---|
| Per-attack-type evaluation | Lead Data Scientist | Breakdown logged: physical, GenAI, recapture APCER separately |
| Adversarial and edge case testing | Lead Data Scientist | Failure modes documented in model card |
| Performance and load testing of API | Software Engineer | p95 < 800 ms at 100 req/min on target hardware |
| Security scan and dependency audit | MLOps Engineer | No critical vulnerabilities; findings remediated or accepted |

---

## 10. MLflow Logging Specification

Every training run must log the following to MLflow:

**Parameters**:
- All Hydra config parameters
- Dataset version hash (from DVC)
- Git commit hash
- Python and library versions

**Metrics** (logged per epoch):
- train_loss, val_loss
- val_apcer_at_1pct_bpcer
- val_audet
- val_auroc
- val_f1
- val_precision, val_recall

**Artifacts**:
- Best model checkpoint (`.pth`)
- Hydra config snapshot
- Confusion matrix plot
- ROC and DET curve plots
- Attention map samples (5 per attack type)
- Model card (Markdown)

---

## 11. Inference Optimisation

| Technique | Applies To | Expected Gain |
|---|---|---|
| Mixed precision (fp16) | All backbones | 1.5–2× throughput |
| torch.compile (PyTorch 2.x) | EfficientNet-B4, ConvNeXt-V2 | 10–30% latency reduction |
| ONNX export + runtime | EfficientNet-B4 (latency fallback) | Further 20–40% on CPU/edge |
| Batch inference | API batch endpoint | Linear throughput scaling |
| Async preprocessing | FastAPI background tasks | Reduces blocking time |
| Model warm-up on startup | All | Eliminates cold-start latency spike |

---

## 12. Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| EVA-02-Large exceeds latency SLO | Medium | High | Increase EfficientNet-B4 ensemble weight; exclude EVA-02 if needed |
| Ensemble overfits to validation set | Low | High | Use small held-out calibration set for weight learning; monitor test gap |
| Dataset class imbalance causes biased threshold | Medium | High | Use weighted sampler; evaluate APCER/BPCER independently |
| GenAI attacks in test set use unseen generator | Medium | Medium | Augment with diverse synthetic artifacts; monitor confidence distribution |
| Training compute exceeds budget | Low | Medium | Checkpoint-restart; prioritise EfficientNet-B4 + ConvNeXt-V2 if budget constrained |

---

## 13. Sign-Off

| Name | Role | Signature | Date |
|---|---|---|---|
| Praveen Mittal | AI Solution Architect | | |
| [Name] | Lead Data Scientist | | |
| [Name] | MLOps Engineer | | |
