# ARGUS: Security & Compliance Document
## Document Control

| Field | Detail |
|---|---|
| **Document ID** | 08_Security_Compliance |
| **Version** | 1.0 |
| **Status** | Draft |
| **Author** | Praveen Mittal |
| **Reviewer** | Security Lead, Compliance Lead, AI Solution Architect |
| **Date Created** | 2026-07-01 |
| **Last Updated** | 2026-07-01 |
| **Related Docs** | [04_SAD.md](../Phase-2/04_SAD.md), [05_DAD.md](../Phase-2/05_DAD.md), [02_BRD.md](../Phase-1/02_BRD.md) |

---

## 1. Purpose

This document defines the complete security and regulatory compliance posture for Project ARGUS. It covers the threat model, security controls, data protection measures, AI governance controls, and evidence requirements for EU AI Act, GDPR, and ISO/IEC 42001 compliance. It is mandatory for the Phase 4 Release Readiness Review.

> **Scope note**: this document describes the target enterprise production
> deployment (Kubernetes, Vault, image signing, on-call rotation, etc.).
> The actual deliverable for the FREUID Challenge 2026 submission is the
> single sandboxed Docker container defined at the repository root
> (`Dockerfile`, `entrypoint.sh`, `prepare_submission.py`) — no Kubernetes
> manifests, Vault instance, or on-call tooling exist in this repository.
> Treat the controls below as design intent for a future production
> deployment, not as claims about what is running today; the controls that
> **are** implemented in this repo (audit logging, RBAC + shared-secret
> auth, drift detection, secret/dependency/SAST scanning) are cross-referenced
> to their actual source files inline.

---

## 2. Regulatory Classification

### 2.1 EU AI Act Classification

| Attribute | Assessment |
|---|---|
| **AI System Type** | High-Risk AI System |
| **Annex III Category** | Biometric-adjacent — identity document verification and fraud detection |
| **Basis for Classification** | ARGUS processes identity documents and makes consequential fraud determinations affecting individuals |
| **Obligations** | Risk management system, technical documentation, data governance, human oversight, accuracy and robustness, post-market monitoring, transparency, logging |
| **Conformity Path** | Internal control (Article 16–25 obligations met through this document and associated controls) |

### 2.2 GDPR Classification

| Attribute | Assessment |
|---|---|
| **Data Controller** | ARGUS operating organisation |
| **Personal Data Processed** | Identity document images (may contain name, photo, date of birth, ID numbers) |
| **Processing Basis** | Legitimate interest / contractual necessity (competition context); explicit consent (production deployment) |
| **Special Category Data** | Potential biometric data — processed ephemerally only; not stored |
| **Data Minimisation Applied** | Yes — EXIF stripped at ingestion; images not persisted after inference |

### 2.3 ISO/IEC 42001 Scope

ARGUS is covered under the organisation's AI Management System (AIMS). This document constitutes the technical control evidence for the ARGUS AI system record.

---

## 3. Threat Model

### 3.1 Threat Modelling Method

STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege).

### 3.2 System Assets

| Asset | Classification | Sensitivity |
|---|---|---|
| FREUID training dataset | Restricted | High |
| Trained model artifacts | Confidential | High |
| MLflow experiment records | Internal | Medium |
| Inference audit logs | Restricted | High |
| API credentials and secrets | Secret | Critical |
| Kubernetes cluster access | Secret | Critical |
| Container images | Internal | Medium |

### 3.3 Threat Register

| ID | Threat | STRIDE | Asset | Likelihood | Impact | Residual Risk | Control |
|---|---|---|---|---|---|---|---|
| T-01 | Attacker submits adversarially crafted document to evade detection | Spoofing | Inference API | Medium | High | Medium | Confidence threshold + human review; model robustness testing |
| T-02 | Attacker probes API to infer model decision boundary via repeated queries | Information Disclosure | Model IP | Medium | Medium | Low | Rate limiting; no raw logit exposure; fraud score only |
| T-03 | Malicious image payload exploits image parsing library (e.g. PIL CVE) | Tampering | API Worker | Low | High | Low | Dependency scanning; container image scanning; input size limits |
| T-04 | Secrets (API keys, DB credentials) leaked into container image or git | Information Disclosure | Secrets | Low | Critical | Low | Gitleaks pre-commit; Trivy image scan; Vault / Secrets Manager |
| T-05 | Unauthorised access to model registry — malicious model promoted | Tampering | Model Artifacts | Low | Critical | Low | RBAC on registry; signed artifacts; promotion requires approval |
| T-06 | Training data poisoning — adversarial samples injected into dataset | Tampering | Training Data | Low | High | Low | Dataset checksum verification; access control on data store |
| T-07 | Denial of service via large batch requests or resource exhaustion | Denial of Service | API | Medium | Medium | Low | Rate limiting; input size gate; HPA autoscaling; circuit breaker |
| T-08 | Audit log tampering — inference records modified or deleted | Tampering | Audit Logs | Low | High | Low | Append-only log sink; immutable storage; access restricted to compliance |
| T-09 | Kubernetes privilege escalation via misconfigured RBAC | Elevation of Privilege | Cluster | Low | Critical | Low | Least-privilege RBAC; namespace isolation; no default service account tokens |
| T-10 | Inference response contains information that reveals PII from training data | Information Disclosure | Training Data | Low | High | Low | No PII in training data; response contains score only |

### 3.4 Risk Acceptance

Residual risks rated **Medium** or above require formal acceptance by the Security Lead and documented below:

| Threat ID | Residual Risk | Accepted By | Date | Conditions |
|---|---|---|---|---|
| T-01 | Medium | Security Lead | 2026-07-02 | Human review mandatory for confidence < 0.70 (default; configurable via `HUMAN_REVIEW_CONFIDENCE_THRESHOLD` — see `src/api/main.py`); model robustness re-evaluated at every release |

---

## 4. Security Controls

### 4.1 Network Security

| Control | Implementation | Status |
|---|---|---|
| TLS 1.2+ on all ingress | NGINX / API Gateway — TLS termination | Required |
| mTLS between internal services | Kubernetes service mesh (Istio / Linkerd) | Required |
| Network policies | Kubernetes NetworkPolicy — deny-all default; explicit allow rules | Required |
| API rate limiting | NGINX rate limit module — 200 req/min per IP | Required |
| DDoS protection | Cloud provider edge protection | Required |

### 4.2 Identity and Access Management

| Control | Implementation |
|---|---|
| RBAC — Kubernetes | Namespace-scoped roles; no cluster-admin in production |
| RBAC — MLflow Model Registry | Named user promotion rights only; no anonymous access |
| RBAC — Data Store | Dataset access limited to ML Engineers with approved access request |
| RBAC — Audit Logs | Read access: Compliance Lead only; write access: API service account only |
| Service Account | Dedicated service account per workload; no default token automount |
| MFA | Required for all human access to production systems |
| Secrets Management | HashiCorp Vault / Cloud Secrets Manager — secrets injected at runtime |

### 4.3 Container and Supply Chain Security

| Control | Implementation | Gate |
|---|---|---|
| Dependency vulnerability scan | Trivy filesystem scan | Block on CRITICAL — every PR |
| Container image scan | Trivy image scan | Block on CRITICAL — every build |
| Image signing | Cosign — signed image digest required for production promotion | Release gate |
| Secret scan | Gitleaks — pre-commit and CI | Block on any secret found |
| SAST | Bandit — static analysis | Block on HIGH — every PR |
| Base image policy | Approved distroless or minimal base images only | Architecture control |
| Pinned dependencies | All versions pinned in requirements files | Code review |

### 4.4 Data Security

| Control | Implementation | Requirement |
|---|---|---|
| EXIF stripping | Applied at ingestion via Pillow / ExifTool | GDPR, FR-16 |
| Encryption at rest | Cloud object store with AES-256 server-side encryption | CR-04 |
| Encryption in transit | TLS on all data movement | CR-04 |
| No inference image storage | Images processed ephemerally; never written to disk or logs | GDPR CR-04 |
| Audit log immutability | Append-only sink; CloudWatch log group with retention policy | CR-03, EU AI Act |
| Dataset access log | All access to training data logged | CR-06 |

### 4.5 Model Security

| Control | Implementation |
|---|---|
| Model artifact signing | Signed hash stored in MLflow alongside artifact |
| Promotion approval | Champion model requires named approval in MLflow before production deployment |
| No raw logit exposure | API returns fraud_score [0,1] only — no raw logits |
| Confidence threshold | Predictions with confidence < 0.70 (default, env-configurable) flagged for human review — limits adversarial probing value |
| Model card | Mandatory for every production model |

---

## 5. EU AI Act Compliance Controls

### 5.1 Risk Management System (Article 9)

| Requirement | Implementation | Evidence |
|---|---|---|
| Risk management system established and maintained | RAID log in [00_Project_Charter.md](../Phase-0/00_Project_Charter.md); threat register in this document | This document + Charter |
| Risks identified, estimated, and evaluated | Threat register Section 3.3 | This document |
| Risk mitigation measures implemented | Security controls Sections 4.1–4.5 | This document |
| Residual risk acceptable | Section 3.4 formal acceptance | This document |
| Risk management reviewed per lifecycle phase | Phase gate reviews include security sign-off | ARB review records |

### 5.2 Data and Data Governance (Article 10)

| Requirement | Implementation | Evidence |
|---|---|---|
| Training data relevant and representative | EDA report confirms dataset covers all three attack types | MLflow EDA artifact |
| Training data free from errors | Dataset validation pipeline; corrupt file exclusion | DVC pipeline log |
| Data minimisation | EXIF stripping; no PII persistence | DAD Section 11 |
| Dataset version controlled and documented | DVC versioning; MLflow dataset tag | DVC remote + MLflow |

### 5.3 Technical Documentation (Article 11)

This document, combined with the following, constitutes the technical documentation package:

- [00_Project_Charter.md](../Phase-0/00_Project_Charter.md) — purpose and intended use
- [01_Architecture_Vision.md](../Phase-0/01_Architecture_Vision.md) — system description
- [04_SAD.md](../Phase-2/04_SAD.md) — detailed design
- [05_DAD.md](../Phase-2/05_DAD.md) — data governance
- [06_ML_Design.md](../Phase-3/06_ML_Design.md) — model design and performance
- [07_Test_Strategy.md](../Phase-3/07_Test_Strategy.md) — validation and testing
- [08_Security_Compliance.md](08_Security_Compliance.md) — this document
- [09_Operations_Runbook.md](09_Operations_Runbook.md) — operational controls

### 5.4 Record-Keeping and Logging (Article 12)

| Requirement | Implementation |
|---|---|
| Automatic logging of system operation | Structured JSON inference log on every request |
| Logs retained for appropriate period | 5 years in append-only immutable store |
| Logs accessible for post-market monitoring | Compliance Lead has read access |
| Log content: request ID, timestamp, result, model version | Confirmed in API logging middleware spec |

### 5.5 Transparency (Article 13)

| Requirement | Implementation |
|---|---|
| System identified as AI system to users | API response includes `model_version` field; API documentation states AI classification |
| Capabilities and limitations documented | Model card for every production model |
| Human oversight information provided | `requires_human_review` flag in every response |

### 5.6 Human Oversight (Article 14)

| Requirement | Implementation |
|---|---|
| Human oversight measures built in by design | `requires_human_review` flag; human review queue (UC-08) |
| Humans able to interpret system output | Confidence score + attention map returned with every prediction |
| Humans able to override system decision | Human review determination overrides model result in audit log |
| Humans able to stop system operation | Operations runbook defines service stop procedure |

### 5.7 Accuracy, Robustness, and Cybersecurity (Article 15)

| Requirement | Implementation |
|---|---|
| Appropriate accuracy levels defined and validated | APCER @ 1% BPCER; AuDET; F1 ≥ 0.90 — Test Strategy Gate |
| Robustness against errors and adversarial inputs | Adversarial test suite (Test Strategy Section 4.4); confidence threshold |
| Cybersecurity measures appropriate to risk | Threat model + controls in this document |

---

## 6. GDPR Compliance Controls

| Article | Requirement | Implementation |
|---|---|---|
| Art. 5 — Data minimisation | Only data necessary for inference processed | EXIF strip; no inference image storage |
| Art. 5 — Storage limitation | No personal data retained after inference | Ephemeral processing; no write to disk |
| Art. 25 — Privacy by design | Controls built into architecture | DAD Section 11; SAD Section 7 |
| Art. 30 — Records of processing | Processing activity record maintained | Data processing record (below) |
| Art. 32 — Security of processing | Encryption at rest and in transit; access controls | Section 4.4 |
| Art. 35 — DPIA | Data Protection Impact Assessment recommended given biometric-adjacent processing | [DPIA to be completed before production launch] |

### Data Processing Record

| Field | Detail |
|---|---|
| Processing Activity | Identity document fraud classification |
| Controller | Argus Security Solutions |
| Purpose | Detect fraudulent identity documents for competition and production use |
| Legal Basis | Legitimate interest / competition participation |
| Categories of Data | Identity document images (may contain biometric-adjacent data) |
| Recipients | No third-party recipients; internal only |
| Retention | Inference logs: 5 years (regulatory); images: not retained |
| Security Measures | TLS, encryption at rest, RBAC, EXIF strip, ephemeral processing |

---

## 7. ISO/IEC 42001 Controls

| Control Domain | Control | Implementation |
|---|---|---|
| AI Risk Management | Risk assessment and treatment | Section 3 threat model; RAID log |
| AI System Objectives | Performance metrics defined | ML Design Section 2 |
| Data Quality | Training data validation and governance | DAD Section 12 |
| AI System Documentation | Technical documentation maintained | Section 5.3 document set |
| Human Oversight | Oversight mechanism built in | Section 5.6 |
| AI Incident Management | Incident classification and response | Operations Runbook Section 7 |
| Monitoring and Measurement | Model and system monitoring | Operations Runbook Section 4 |
| Continual Improvement | Drift detection; retraining process | Operations Runbook Section 9 |

---

## 8. Security Testing Evidence Requirements

The following security evidence must be present in the release evidence pack before production deployment:

| Evidence Item | Tool | Frequency | Retained |
|---|---|---|---|
| Dependency scan report | Trivy | Every release | Yes — 3 years |
| Container image scan report | Trivy | Every release | Yes — 3 years |
| Secret scan report | Gitleaks | Every release | Yes — 3 years |
| SAST report | Bandit | Every release | Yes — 3 years |
| Threat model review sign-off | This document | Per major release | Yes — 5 years |
| DPIA (if required) | Manual | Before production | Yes — 5 years |
| EXIF strip audit result | pytest | Every release | Yes — 3 years |
| Penetration test report | External | Annually | Yes — 5 years |

---

## 9. Compliance Review Schedule

| Review | Frequency | Owner | Output |
|---|---|---|---|
| Security control review | Per release | Security Lead | Updated Section 4 |
| Threat model review | Quarterly | Security Lead | Updated threat register |
| EU AI Act conformity review | Annually | Compliance Lead | Conformity assessment update |
| GDPR processing record review | Annually | Compliance Lead | Updated data processing record |
| ISO/IEC 42001 internal audit | Annually | Compliance Lead | Audit finding report |
| Penetration test | Annually | External | Pen test report |

---

## 10. Open Compliance Issues

| ID | Issue | Owner | Target |
|---|---|---|---|
| CC-01 | DPIA not yet completed — required before production launch | Compliance Lead | Phase 4 |
| CC-02 | Penetration test not yet scheduled | Security Lead | Phase 4 |
| CC-03 | EU AI Act conformity self-assessment to be finalised | Compliance Lead | Phase 4 |
| CC-04 | Confirm mTLS implementation approach (Istio vs. Linkerd) | Infrastructure Lead | End of Phase 2 |

---

## 11. Sign-Off

| Praveen Mittal | AI Solution Architect | Approved | 2026-07-02 |
| Security Lead | Security Lead | Approved | 2026-07-02 |
| Compliance Lead | Compliance Lead | Approved | 2026-07-02 |
| ARB Chair | ARB Chair | Approved | 2026-07-02 |
