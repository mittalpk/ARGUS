# ARGUS: Identity Document Fraud Detection

A production-grade AI system designed to detect next-generation identity document fraud, built for the **FREUID Challenge 2026** (hosted at IJCAI-ECAI 2026).

ARGUS is designed to address three primary types of document forgery:
1. **Physical Manipulations**: Alterations made directly on physical document substrates.
2. **GenAI-Driven Edits**: Digital manipulations generated using generative AI tools.
3. **Print-and-Capture (Recapture) Attacks**: Forged documents that are printed and re-photographed to mask digital editing artifacts.

---

## Project Status & Roadmap

This project is currently in active development. The system architecture, compliance checkpoints, and delivery roadmap are guided by the [Enterprise AI Project Runbook](docs/project_runbook.md).

### Planned Repository Structure
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
The system will utilize an ensemble of diverse deep learning backbones to balance latency and accuracy:
- **EVA-02-Large** / **ConvNeXt-V2-Base**: High-capacity feature extractors for fine-grained texture and pattern analysis.
- **EfficientNet-B4**: A lightweight backbone optimized for lower-latency inference.

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
Ensure your Kaggle API credentials are configured in `~/.kaggle/kaggle.json`:
```bash
kaggle competitions download -c the-freuid-challenge-2026-ijcai-ecai -p data/
unzip data/the-freuid-challenge-2026-ijcai-ecai.zip -d data/
```

---

## Author
**Praveen Mittal**  
[praveenmittal.com](https://praveenmittal.com) | [LinkedIn](https://linkedin.com/in/praveen-mittal)

---

## License
Licensed under the Apache 2.0 License. See [LICENSE](LICENSE) for details.

