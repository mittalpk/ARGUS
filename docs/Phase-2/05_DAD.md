# ARGUS: Data Architecture Document (DAD)
## Document Control

| Field | Detail |
|---|---|
| **Document ID** | 05_DAD |
| **Version** | 1.0 |
| **Status** | Draft |
| **Author** | Praveen Mittal |
| **Reviewer** | Lead Data Scientist, Security Lead, Compliance Lead |
| **Date Created** | 2026-06-30 |
| **Last Updated** | 2026-06-30 |
| **Related Docs** | [04_SAD.md](04_SAD.md), [02_BRD.md](../Phase-1/02_BRD.md) |

---

## 1. Purpose

This document defines the data architecture for Project ARGUS — covering data sources, ingestion, preprocessing, augmentation, versioning, lineage, storage, access controls, privacy controls, and the data contracts between pipeline stages.

---

## 2. Data Sources

| ID | Source | Format | Access Method | Owner |
|---|---|---|---|---|
| DS-01 | FREUID Challenge 2026 — Training Set | JPEG / PNG images + CSV labels | Kaggle API | Competition organisers |
| DS-02 | FREUID Challenge 2026 — Test Set | JPEG / PNG images (no labels) | Kaggle API | Competition organisers |
| DS-03 | Pre-trained model weights | PyTorch `.pth` / HuggingFace | HuggingFace Hub / timm | Open source |
| DS-04 | Augmented training set | JPEG / PNG (generated) | Local / object store | ARGUS team |

---

## 3. Dataset Characteristics

| Attribute | Detail |
|---|---|
| Task | Binary classification — genuine vs. fraudulent identity document |
| Attack Types | Physical manipulation, GenAI digital edit, Print-and-capture recapture |
| Input Format | RGB images, variable resolution |
| Label Format | Binary label per image (0 = genuine, 1 = fraudulent) |
| Class Balance | To be confirmed during EDA (Phase 3 Sprint 1) |
| Expected Size | To be confirmed after download; estimated 10,000–100,000 images |

---

## 4. Data Pipeline Overview

```
[Kaggle API]
      │
      ▼
[Ingestion]
  • Download raw archive
  • Verify checksum
  • Extract to data/raw/
  • Log dataset version and hash
      │
      ▼
[Validation]
  • Schema check (image readability, label presence)
  • Duplicate detection
  • Class balance audit
  • Flag corrupt or unreadable files
      │
      ▼
[Privacy Controls]
  • Strip EXIF metadata from all images
  • Verify no PII persists after stripping
      │
      ▼
[Splitting]
  • Deterministic train / validation / test split
  • Seed locked per DVC run
  • Stratified by label and attack type
      │
      ▼
[Preprocessing]
  • Resize to target resolution per backbone
  • Normalise to ImageNet mean/std
  • Convert to tensor
      │
      ▼
[Augmentation — training only]
  • Random horizontal flip
  • Random rotation (±15°)
  • Colour jitter (brightness, contrast, saturation)
  • Random cutout / erasing
  • Optional: MixUp, CutMix
      │
      ▼
[Versioned Dataset]
  • DVC-tracked data artefact
  • SHA-256 hash locked
  • Registered in DVC remote
```

---

## 5. Data Splits

| Split | Proportion | Usage | Label Available |
|---|---|---|---|
| Train | 70% | Model training | Yes |
| Validation | 15% | Hyperparameter tuning, threshold selection | Yes |
| Test | 15% | Final held-out evaluation — used once only | Yes (held by pipeline) |
| Competition Test | External | Final competition submission scoring | No (held by FREUID) |

**Rules**:
- Test split is accessed exactly once — at final model evaluation before competition submission
- Validation split is the only split used for iterative model improvement
- Split seed is locked in DVC configuration and must not be changed after Phase 3 Sprint 1

---

## 6. Preprocessing Specification

| Step | Detail | Applies To |
|---|---|---|
| EXIF strip | Remove all EXIF, IPTC, XMP metadata using Pillow or ExifTool | All splits |
| Resize | EfficientNet-B4: 380×380; EVA-02-Large: 448×448; ConvNeXt-V2-Base: 384×384 | All splits |
| Normalisation | ImageNet mean [0.485, 0.456, 0.406], std [0.229, 0.224, 0.225] | All splits |
| Format conversion | PIL → PyTorch tensor (CHW float32) | All splits |
| Corrupt file handling | Log and exclude; alert if > 0.5% of dataset | All splits |

---

## 7. Augmentation Specification

All augmentations applied during training only. Validation and test sets receive preprocessing only (no augmentation).

| Augmentation | Parameters | Probability |
|---|---|---|
| Random horizontal flip | — | 0.5 |
| Random rotation | ±15 degrees | 0.5 |
| Colour jitter | brightness=0.2, contrast=0.2, saturation=0.2, hue=0.05 | 0.5 |
| Random erasing / cutout | scale=(0.02, 0.2), ratio=(0.3, 3.3) | 0.3 |
| MixUp | alpha=0.4 | 0.3 |
| CutMix | alpha=1.0 | 0.3 |

**Note**: MixUp and CutMix are applied at the batch level during training. They are not applied simultaneously (mutually exclusive per batch with 30% each, 40% neither).

---

## 8. Data Versioning Strategy

| Tool | Purpose |
|---|---|
| DVC | Track dataset files, preprocessing configs, and pipeline steps |
| Git | Track DVC `.dvc` pointer files and pipeline YAML |
| Remote Storage | DVC remote (S3 / GCS / local NAS) for actual data files |

**Versioning Rules**:
- Every experiment must reference a locked DVC dataset version
- Dataset version hash must be logged to MLflow alongside model metrics
- Changes to preprocessing logic increment the dataset version
- Test split pointer is read-only after first use

**DVC Pipeline Stages** (`dvc.yaml`):
```
stages:
  ingest:
    cmd: python src/data/ingestion.py
    deps: [scripts/download_data.sh]
    outs: [data/raw/]

  validate:
    cmd: python src/data/validate.py
    deps: [data/raw/]
    outs: [data/validated/]

  preprocess:
    cmd: python src/data/preprocess.py
    deps: [data/validated/, configs/data/default.yaml]
    outs: [data/processed/]

  split:
    cmd: python src/data/split.py
    deps: [data/processed/]
    outs: [data/splits/train/, data/splits/val/, data/splits/test/]
```

---

## 9. Data Lineage

```
FREUID 2026 Kaggle Release
        │  (DS-01, DS-02)
        ▼
  data/raw/              ← DVC: hash_raw_v1
        │
        ▼
  data/validated/        ← DVC: hash_validated_v1
        │
        ▼
  data/processed/        ← DVC: hash_processed_v1
        │
        ├── data/splits/train/   ← Used in training run exp_001..N
        ├── data/splits/val/     ← Used in all evaluations
        └── data/splits/test/    ← Used once at final evaluation
```

Full lineage is queryable via MLflow by cross-referencing dataset version tag with run ID.

---

## 10. Storage Architecture

| Store | Type | Contents | Access Control | Retention |
|---|---|---|---|---|
| `data/raw/` | Local / Object Store | Raw downloaded images | Team — read/write | Project duration |
| `data/processed/` | Local / Object Store | Preprocessed tensors | Team — read/write | Project duration |
| `data/splits/` | Local / Object Store | Split datasets | ML Engineers — read only | Project duration |
| DVC Remote | Object Store (S3/GCS) | DVC-tracked artefacts | MLOps — read/write | Project duration + 1 year |
| MLflow Artefact Store | Object Store | Model artifacts, metrics, configs | ML Engineers | 3 years (audit) |
| Audit Log Store | Append-only log sink | Inference request logs | Compliance — read only | 5 years (regulatory) |

---

## 11. Privacy and Data Protection Controls

| Control | Detail | Requirement |
|---|---|---|
| EXIF stripping | Applied at ingestion before any processing | GDPR, FR-16 |
| Ephemeral Storage | Images requiring human review are encrypted and stored in a secure bucket with a strict 24-hour TTL; all other images are processed entirely in memory | GDPR, CR-04, UC-08 |
| Data access RBAC | Dataset access restricted to named team members with approved access | CR-04 |
| Dataset usage record | Signed record of which datasets were used under which licences | CR-06 |
| Data retention policy | Inference logs retained 5 years; raw training data retained for project duration only | CR-05 |
| Anonymisation audit | Post-ingestion audit confirms EXIF strip was successful | CR-05 |

---

## 12. Data Quality Rules

| Rule | Threshold | Action on Breach |
|---|---|---|
| Corrupt image rate | < 0.5% of dataset | Alert and exclude; fail pipeline if > 2% |
| Label completeness | 100% of training images labelled | Fail pipeline |
| Class imbalance | > 5:1 ratio triggers review | Log warning; consider weighted sampling |
| Duplicate image rate | < 0.1% | Alert; deduplicate before training |
| Resolution floor | Minimum 128×128 pixels | Exclude and log |

---

## 13. Data Contracts Between Pipeline Stages

| Stage Output → Stage Input | Schema |
|---|---|
| Raw images → Validation | JPEG/PNG file, RGB, any resolution |
| Validated images → Preprocessing | JPEG/PNG file, RGB, ≥ 128×128, no corrupt files |
| Preprocessed tensors → Dataset loader | PyTorch tensor, CHW float32, normalised, target resolution per backbone |
| Dataset loader → Training | Batched tensors (B, C, H, W), labels (B,) as long tensor |
| Inference API → Preprocessing | Base64-encoded or multipart image, JPEG/PNG, ≤ 10 MB |

---

## 14. Open Data Issues

| ID | Issue | Owner | Target |
|---|---|---|---|
| DA-01 | Dataset size and class balance not yet confirmed — depends on Kaggle release | Data Engineer | Phase 3 Sprint 1 EDA |
| DA-02 | Confirm whether FREUID 2026 dataset includes attack type labels or binary only | Lead Data Scientist | Phase 3 Sprint 1 |
| DA-03 | DVC remote storage provider to be confirmed | MLOps Engineer | Phase 2 completion |

---

## 15. Sign-Off

| Name | Role | Signature | Date |
|---|---|---|---|
| Praveen Mittal | AI Solution Architect | | |
| [Name] | Lead Data Scientist | | |
| [Name] | Security Lead | | |
| [Name] | Compliance Lead | | |
