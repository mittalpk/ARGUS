# ARGUS: Project Charter
## Document Control

| Field | Detail |
|---|---|
| **Document ID** | 00_Project_Charter |
| **Version** | 1.0 |
| **Status** | Draft |
| **Author** | Praveen Mittal |
| **Reviewer** | [ARB / Sponsor] |
| **Date Created** | 2026-06-30 |
| **Last Updated** | 2026-06-30 |

---

## 1. Project Overview

| Field | Detail |
|---|---|
| **Project Name** | ARGUS |
| **Full Name** | Identity Document Fraud Detection System |
| **Competition** | FREUID Challenge 2026 (IJCAI-ECAI 2026) |
| **Project Lead** | Praveen Mittal |
| **Sponsor** | [INSERT NAME] |
| **Start Date** | [INSERT DATE] |
| **Target Completion** | [INSERT DATE — competition submission deadline] |

### Problem Statement

Identity document fraud — including physical manipulations, GenAI-driven digital edits, and print-and-capture (recapture) attacks — represents a growing threat to identity verification systems. ARGUS is an AI system designed to detect these attack vectors with production-grade reliability, governance, and explainability.

### Business Case

- Participation in FREUID Challenge 2026 positions the team at the frontier of document fraud detection research
- Winning or placing competitively provides credibility, IP value, and potential commercial application
- The system architecture is designed to be reusable as a production inference platform beyond the competition

---

## 2. Objectives

| # | Objective | Measure of Success |
|---|---|---|
| 1 | Detect physical document manipulations with high accuracy | APCER minimised at 1% BPCER threshold |
| 2 | Detect GenAI-driven digital document edits | AuDET score maximised on challenge leaderboard |
| 3 | Detect print-and-capture recapture attacks | All three attack types covered in test evaluation |
| 4 | Deliver production-grade system architecture | All phase deliverables complete and approved |
| 5 | Meet regulatory compliance requirements | EU AI Act, GDPR, ISO/IEC 42001 controls in place |

---

## 3. Scope

### In Scope

- Document fraud detection for the three attack types: physical manipulation, GenAI edits, recapture attacks
- Ensemble model architecture using EVA-02-Large, ConvNeXt-V2-Base, and EfficientNet-B4
- Training and evaluation on FREUID Challenge 2026 dataset
- REST API inference service
- MLOps pipeline: experiment tracking, model registry, CI/CD
- Security and compliance documentation
- Monitoring and operational runbook for production deployment

### Out of Scope

- Real-time biometric face matching or identity verification beyond document fraud
- Integration with third-party identity platforms
- Custom hardware or edge deployment
- Non-English document types unless covered in the competition dataset
- Human review workflow tooling

---

## 4. Deliverables by Phase

| Phase | Key Deliverables |
|---|---|
| Phase 0 | Project Charter, Architecture Vision, Stakeholder Matrix, RAID Log |
| Phase 1 | BRD, Use Case Specification, Initial Product Backlog |
| Phase 2 | SAD, DAD, ADRs, API Contracts |
| Phase 3 | ML Design, Test Strategy, Source Code, Model Artifacts |
| Phase 4 | Security & Compliance Docs, Operations Runbook, Production Deployment |
| Phase 5 | Monitoring Dashboards, Audit Evidence, Model Performance Reports |

---

## 5. Team Structure

| Role | Name | Responsibility |
|---|---|---|
| AI Solution Architect / Project Lead | Praveen Mittal | Architecture, technical leadership, delivery |
| Business Sponsor | [NAME] | Funding, strategic decisions, executive escalation |
| Project Manager | [NAME] | Delivery governance, scheduling, risk management |
| Lead Data Scientist | [NAME] | Model design, experimentation, evaluation |
| MLOps Engineer | [NAME] | Pipelines, CI/CD, model registry, deployment |
| Software Engineer | [NAME] | API development, code quality, testing |
| Data Engineer | [NAME] | Data ingestion, preprocessing, augmentation |
| Security Lead | [NAME] | Threat model, vulnerability management, controls |
| Compliance Lead | [NAME] | EU AI Act, GDPR, ISO/IEC 42001 compliance |
| Infrastructure Lead | [NAME] | Cloud infrastructure, Kubernetes, networking |

---

## 6. Governance

| Forum | Frequency | Purpose |
|---|---|---|
| Architecture Review Board (ARB) | Per phase gate | Architecture design and decision approval |
| Sprint Review | End of each 2-week sprint | Demonstrate working software to stakeholders |
| Steering Group | Monthly | Strategic direction, budget review, escalation |
| Operations Review | Weekly (Phase 5) | Service health, incident review |
| Model Governance Review | Monthly (Phase 5) | Drift, performance, retraining decisions |

---

## 7. Budget

| Category | Estimated Cost | Notes |
|---|---|---|
| Compute — model training | [INSERT] | GPU cloud instances, training runs |
| Compute — inference hosting | [INSERT] | API serving, staging and production |
| Storage | [INSERT] | Dataset, artifacts, logs |
| Tooling and licences | [INSERT] | Experiment tracking, monitoring, CI/CD |
| Compliance and audit | [INSERT] | External review if required |
| **Total** | **[INSERT]** | |

---

## 8. Timeline

| Milestone | Target Date |
|---|---|
| Phase 0 complete — Charter and Vision approved | [DATE] |
| Phase 1 complete — BRD signed off | [DATE] |
| Phase 2 complete — Architecture approved | [DATE] |
| Phase 3 MVP — baseline model running | [DATE] |
| Phase 3 complete — champion model validated | [DATE] |
| Phase 4 complete — production deployment | [DATE] |
| Competition submission deadline | [FREUID 2026 DEADLINE] |

---

## 9. Constraints

| Constraint | Description |
|---|---|
| Competition deadline | Submission must be made before the FREUID Challenge 2026 deadline |
| Dataset access | Training only on the approved FREUID competition dataset |
| Regulatory | Must comply with EU AI Act as a high-risk AI system using biometric data |
| Data privacy | No PII storage; EXIF stripping required at ingestion |
| Compute budget | GPU compute expenditure must stay within approved budget |

---

## 10. RAID Log

### Risks

| ID | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | Model does not converge to target metrics before competition deadline | Medium | High | Early baseline experiment; fallback to EfficientNet-B4 ensemble |
| R-02 | Dataset quality is lower than expected | Medium | High | EDA in Phase 3 Week 1; augmentation plan ready |
| R-03 | Compute budget exceeded by training runs | Medium | Medium | Cost monitoring; checkpoint-restart strategy |
| R-04 | Compliance requirements delay architecture sign-off | Low | Medium | Engage compliance lead from Phase 0 |
| R-05 | Key team member unavailable | Low | High | Cross-train on critical paths; document all decisions |

### Assumptions

| ID | Assumption |
|---|---|
| A-01 | The FREUID 2026 dataset is available and accessible via Kaggle API |
| A-02 | GPU compute infrastructure can be provisioned within budget |
| A-03 | The competition evaluation server accepts API-based submissions |
| A-04 | Pre-trained model weights are available for EVA-02-Large and ConvNeXt-V2 |

### Issues

| ID | Issue | Owner | Status |
|---|---|---|---|
| I-01 | [No issues at initiation] | — | — |

### Dependencies

| ID | Dependency | Owner | Impact if Delayed |
|---|---|---|---|
| D-01 | FREUID 2026 dataset release | Competition organisers | Phase 3 training blocked |
| D-02 | GPU cloud compute provisioned | Infrastructure Lead | Phase 3 cannot start |
| D-03 | Pre-trained model checkpoints available | Lead Data Scientist | Model training delayed |

---

## 11. Sign-Off

By signing below, the signatories confirm they have read and approved this Project Charter.

| Name | Role | Signature | Date |
|---|---|---|---|
| Praveen Mittal | AI Solution Architect / Project Lead | | |
| [Name] | Business Sponsor | | |
| [Name] | Project Manager | | |
