# ARGUS: Identity Document Fraud Detection

A production-grade AI system designed to detect next-generation identity document fraud, built for the **FREUID Challenge 2026** (hosted at IJCAI-ECAI 2026).

ARGUS is designed to address three primary types of document forgery:
1. **Physical Manipulations**: Alterations made directly on physical document substrates.
2. **GenAI-Driven Edits**: Digital manipulations generated using generative AI tools.
3. **Print-and-Capture (Recapture) Attacks**: Forged documents that are printed and re-photographed to mask digital editing artifacts.

---

## Project Status

This repository is the reproducibility package for Team ARGUS's FREUID Challenge 2026 submission. The system architecture, compliance checkpoints, and delivery history are documented in the [Enterprise AI Project Runbook](docs/project_runbook.md).

The Docker image ships with a trained EfficientNet-B4 champion checkpoint
(`checkpoints/champion_efficientnet_b4.pth`, produced by
`scripts/train_champion_checkpoint.sh`) baked in — see
[Reproducing the Submission](#reproducing-the-submission) below to rebuild
and verify it end-to-end.

### Repository Structure
```text
ARGUS/
├── docs/                           # Architecture and design documentation
│   ├── project_runbook.md          # End-to-end project runbook
│   ├── 00_Project_Charter.md       # Project Charter (Phase 0)
│   ├── 01_Architecture_Vision.md   # TOGAF Phase A Architecture Vision (Phase 0)
│   ├── 02_BRD.md                   # Business Requirements Document (Phase 1)
│   ├── 03_Use_Case_Specification.md# Use Case Specifications (Phase 1)
│   ├── 04_SAD.md                   # Solution Architecture Document (Phase 2)
│   ├── 05_DAD.md                   # Data Architecture Document (Phase 2)
│   ├── adr/                        # Architecture Decision Records (Phase 2)
│   ├── 06_ML_Design.md             # AI/ML Design Document (Phase 3)
│   ├── 07_Test_Strategy.md         # Test Strategy (Phase 3)
│   ├── 08_Security_Compliance.md   # Security & Compliance (Phase 4)
│   └── 09_Operations_Runbook.md    # Operations Runbook (Phase 4)
├── src/                            # Core source code
│   ├── data/                       # Preprocessing and augmentation pipelines
│   ├── models/                     # Model definitions and ensembles
│   └── training/                   # Training and evaluation scripts
├── configs/                        # Hydra configuration files
└── notebooks/                      # Exploratory data analysis (EDA)
```

---

## Technical Approach

### Model Architecture
ARGUS is built around an ensemble of diverse deep learning backbones that trade off latency and accuracy:
- **EVA-02-Large** / **ConvNeXt-V2-Base**: High-capacity feature extractors for fine-grained texture and pattern analysis.
- **EfficientNet-B4**: A lightweight backbone optimized for lower-latency inference — this is the backbone shipped as the Docker image's default champion checkpoint, since it is the fastest to train and serve while the full three-backbone ensemble (`--model_name ensemble`) remains available for teams with the compute budget to train all three.

### Evaluation Metrics
We optimize for the competition's primary metric along with key production-focused metrics:
- **AuDET** (Area under the Detection Error Trade-off curve): Evaluates overall system trade-offs.
- **APCER @ 1% BPCER**: Measures the rate of fraudulent documents accepted when the false rejection rate of genuine documents is capped at 1%.

---

## Quick Start

### 1. Setup Environment
```bash
git clone https://github.com/praveenmittal/ARGUS
cd ARGUS
bash scripts/setup.sh
```

### 2. Dataset Acquisition
Ensure your Kaggle API credentials are configured in `~/.kaggle/kaggle.json` or a local `.env` (see `.env` — never commit real credentials):
```bash
bash scripts/download_data.sh
```

---

## Reproducing the Submission

1. **Download the dataset** (above) — this populates `data/the-freuid-challenge-2026/`.
2. **Train the champion checkpoint** that ships inside the Docker image:
   ```bash
   bash scripts/train_champion_checkpoint.sh
   ```
   This runs the same ingestion → split → train → model-gate pipeline used
   in production on a fixed-seed stratified sample of the training set, and
   writes `checkpoints/champion_efficientnet_b4.pth`. Raise `SAMPLE_PER_CLASS`
   and `EPOCHS` (env vars) to train on more data for a stronger model.
3. **Generate real compliance evidence** from that run:
   ```bash
   pip install -r requirements-dev.txt
   python scripts/package_compliance_evidence.py
   ```
4. **Build and verify the sandboxed Docker image**:
   ```bash
   docker build -t argus-freuid:local .
   docker run --rm --network none \
     -v "$(pwd)/data/the-freuid-challenge-2026/public_test:/data:ro" \
     -v "$(pwd)/out:/submissions" \
     argus-freuid:local
   ```
   Verify `out/submission.csv` has one `id,label` row per input image.

See the FREUID Challenge 2026 reproducibility page for the full prize-eligibility checklist and Kaggle forum reply requirements.

---

## Author
**Praveen Mittal**  
[praveenmittal.com](https://praveenmittal.com) | [LinkedIn](https://linkedin.com/in/praveen-mittal)

---

## License
Licensed under the Apache 2.0 License. See [LICENSE](LICENSE) for details.

