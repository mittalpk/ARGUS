# ADR-004: DVC for Dataset and Pipeline Versioning

## Document Control

| Field | Detail |
|---|---|
| **ADR ID** | ADR-004 |
| **Title** | DVC for Dataset and Pipeline Versioning |
| **Status** | Accepted |
| **Author** | Praveen Mittal |
| **Date** | 2026-06-30 |
| **Deciders** | AI Solution Architect, ARB |

---

## Context

Every training run must be reproducible from the exact dataset version and preprocessing configuration used. This requires dataset versioning tied to the git history.

---

### Options Considered

| Option | Pros | Cons |
|---|---|---|
| **DVC** | Git-native; supports remote storage backends; pipeline DAG; integrates with MLflow | Requires DVC remote setup |
| Git LFS | Simple; built into Git | Not designed for large ML datasets; bandwidth-heavy |
| Delta Lake / Iceberg | Enterprise data versioning | Overkill for image datasets; complex setup |
| Manual versioning (dated folders) | Simple | Not reproducible; error-prone; no lineage |

### Decision

**DVC** (latest stable) with a cloud object store remote (S3 / GCS — see OA-03).

### Rationale

- DVC `.dvc` pointer files are committed to Git, making dataset versions part of the git history
- Pipeline stages in `dvc.yaml` enforce reproducibility: each stage caches outputs and re-runs only when inputs change
- Cross-references dataset version hash into MLflow run metadata, satisfying FR-21
- Handles large image datasets efficiently via remote storage

### Consequences

- **Positive**: Full dataset reproducibility; pipeline caching reduces redundant compute; lineage traceable in git
- **Negative**: Team must learn DVC workflow; remote storage must be provisioned
- **Neutral**: DVC and MLflow complement each other — DVC owns data lineage, MLflow owns model lineage

---

## Status

**Accepted**

---

## References

- [04_SAD.md](../04_SAD.md)
- [02_BRD.md](../../Phase-1/02_BRD.md)
- [01_Architecture_Vision.md](../../Phase-0/01_Architecture_Vision.md)
