# ARGUS: Identity Document Fraud Detection

A production-grade AI system designed to detect next-generation identity document fraud, built for the **FREUID Challenge 2026** (hosted at IJCAI-ECAI 2026).

ARGUS addresses three primary types of document forgery:

1. **Physical Manipulations**: Alterations made directly on physical document substrates.
2. **GenAI-Driven Edits**: Digital manipulations generated using generative AI tools.
3. **Print-and-Capture (Recapture) Attacks**: Forged documents that are printed and re-photographed to mask digital editing artifacts.

> **Current Status**: Production Ready — Phase 3 (Development & QA)
> Full lifecycle is governed by the [Enterprise AI Project Runbook](docs/project_runbook.md).

---

## Repository Structure

```text
ARGUS/
├── data/                           # Raw and processed datasets (gitignored)
│   └── the-freuid-challenge-2026/  # Kaggle competition data
├── docs/                           # Architecture and design documentation
│   ├── project_runbook.md          # End-to-end project execution runbook
│   ├── Phase-0/                    # Preliminary & Vision (Phase 0)
│   │   ├── 00_Project_Charter.md
│   │   ├── 01_Architecture_Vision.md
│   │   ├── 00_Stakeholder_Matrix.md
│   │   ├── 00_Kickoff_Agenda.md
│   │   └── 00_ARB_Vision_Review.md
│   ├── Phase-1/                    # Business & Requirements (Phase 1)
│   │   ├── 02_BRD.md
│   │   ├── 03_Use_Case_Specification.md
│   │   └── 04_Requirements_Walkthrough.md
│   ├── Phase-2/                    # Architecture & Design (Phase 2)
│   │   ├── 04_SAD.md
│   │   ├── 05_DAD.md
│   │   ├── 06_ARB_Design_Sign_Off.md
│   │   └── adr/                    # Architecture Decision Records
│   ├── Phase-3/                    # Development & QA (Phase 3)
│   │   ├── 06_ML_Design.md
│   │   └── 07_Test_Strategy.md
│   └── Phase-4/                    # Deployment & Operations (Phase 4)
│       ├── 08_Security_Compliance.md
│       └── 09_Operations_Runbook.md
├── notebooks/                      # Exploratory data analysis (EDA)
│   └── 01_EDA.ipynb
├── scripts/                        # Utility and setup scripts
│   ├── setup.sh                    # Environment bootstrap script
│   └── download_data.sh            # Kaggle dataset download helper
├── src/                            # Core source code
│   ├── data/                       # Preprocessing and augmentation pipelines
│   ├── models/                     # Model definitions and ensembles
│   ├── training/                   # Training and evaluation scripts
│   └── api/                        # FastAPI inference service
├── configs/                        # Hydra configuration files
│   ├── model/
│   ├── training/
│   └── inference/
├── tests/                          # Unit, integration, and performance tests
│   ├── unit/
│   ├── integration/
│   └── performance/
├── .github/
│   └── workflows/                  # CI/CD pipeline definitions
├── requirements.txt                # Python dependencies
├── pyproject.toml                  # Project metadata and tooling config
├── Dockerfile                      # Production container image
└── LICENSE                         # Apache 2.0 License
```

---

## Technical Approach

### Model Architecture

The system utilises an ensemble of diverse deep learning backbones to balance latency and accuracy:

| Backbone | Role | Trade-off |
|---|---|---|
| **EVA-02-Large** | High-capacity feature extractor | Highest accuracy, higher latency |
| **ConvNeXt-V2-Base** | Fine-grained texture/pattern analysis | Strong accuracy, moderate latency |
| **EfficientNet-B4** | Lightweight backbone | Lowest latency, optimised for production |

### Evaluation Metrics

| Metric | Description | Target |
|---|---|---|
| **AuDET** | Area under the Detection Error Trade-off curve | Maximise |
| **APCER @ 1% BPCER** | Fraudulent acceptance rate when genuine rejection rate ≤ 1% | Minimise |

---

## Quick Start

### Prerequisites

- Python 3.10
- Conda or virtualenv
- Kaggle API credentials (`~/.kaggle/kaggle.json`)
- Docker (for containerised inference)

### 1. Clone & Bootstrap Environment

```bash
git clone https://github.com/praveenmittal/ARGUS
cd ARGUS
bash scripts/setup.sh
```

`setup.sh` will create a virtual environment, install all dependencies from `requirements.txt`, and configure pre-commit hooks.

### 2. Dataset Acquisition

```bash
bash scripts/download_data.sh
# Or manually:
kaggle competitions download -c the-freuid-challenge-2026-ijcai-ecai -p data/
unzip data/the-freuid-challenge-2026-ijcai-ecai.zip -d data/the-freuid-challenge-2026/
```

### 3. Run EDA

```bash
jupyter notebook notebooks/01_EDA.ipynb
```

### 4. Train a Model

To train model backbones (e.g. EfficientNet baseline):
```bash
python src/training/train.py model=efficientnet
```

### 5. Run Reproducibility Sandbox (Docker Verification)

Organizers execute model inference using the Docker sandbox contract:
```bash
# Build the reproducibility image
docker build -t freuid-repro:local .

# Run inference in a zero-network sandbox
docker run --rm \
  --network none \
  -v /path/to/flat/test/images:/data:ro \
  -v "$(pwd)/out:/submissions" \
  freuid-repro:local
```
This writes the formatted predictions output to `out/submission.csv`.

---

## Development Workflow

This project follows a trunk-based development model:

1. Branch from `main` using the convention `feature/<phase>-<short-description>`
2. Implement changes, ensuring all tests pass: `pytest tests/`
3. Run linting and formatting: `ruff check . && ruff format .`
4. Open a Pull Request — CI/CD gates must pass before merge
5. Squash-merge into `main`

---

## Compliance & Governance

ARGUS is designed with regulatory compliance embedded from Phase 0:

- **EU AI Act** (High-Risk AI System — Biometric/Identity): Risk management, human oversight, and transparency requirements built into the architecture.
- **GDPR**: No PII is stored beyond ephemeral processing; EXIF stripping applied at ingestion.
- **ISO/IEC 42001**: AI management system controls documented in `docs/08_Security_Compliance.md`.

---

## Author

**Praveen Mittal**
[praveenmittal.com](https://praveenmittal.com) | [LinkedIn](https://linkedin.com/in/praveen-mittal)

---

## License

Licensed under the Apache 2.0 License. See [LICENSE](LICENSE) for details.
