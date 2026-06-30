# ARGUS: Stakeholder Matrix
## Document Control

| Field | Detail |
|---|---|
| **Document ID** | 00_Stakeholder_Matrix |
| **Version** | 1.0 |
| **Status** | Draft |
| **Author** | Praveen Mittal |
| **Last Updated** | 2026-06-30 |

---

## 1. Stakeholder Register

| ID | Stakeholder | Role | Organisation | Contact | Influence | Interest |
|---|---|---|---|---|---|---|
| S-01 | Praveen Mittal | AI Solution Architect / Project Lead | [Org] | praveenmittal.com | High | High |
| S-02 | [Name] | Business Sponsor | [Org] | [Email] | High | High |
| S-03 | [Name] | Project Manager | [Org] | [Email] | High | High |
| S-04 | [Name] | Lead Data Scientist | [Org] | [Email] | Medium | High |
| S-05 | [Name] | MLOps Engineer | [Org] | [Email] | Medium | High |
| S-06 | [Name] | Software Engineer | [Org] | [Email] | Low | High |
| S-07 | [Name] | Data Engineer | [Org] | [Email] | Low | High |
| S-08 | [Name] | Security Lead | [Org] | [Email] | High | Medium |
| S-09 | [Name] | Compliance Lead | [Org] | [Email] | High | Medium |
| S-10 | [Name] | Infrastructure Lead | [Org] | [Email] | Medium | Medium |
| S-11 | [Name] | Operations Lead | [Org] | [Email] | Medium | Medium |
| S-12 | FREUID Challenge Organisers | Competition Authority | IJCAI-ECAI 2026 | [URL] | High | Low |

---

## 2. RACI Matrix by Phase

**Key**: R = Responsible | A = Accountable | C = Consulted | I = Informed

| Activity | AI Architect | Project Manager | Business Sponsor | Lead Data Scientist | MLOps Engineer | Software Engineer | Security Lead | Compliance Lead | Infra Lead | Ops Lead |
|---|---|---|---|---|---|---|---|---|---|---|
| **Phase 0: Vision** | | | | | | | | | | |
| Project Charter | A/R | R | C | I | I | I | C | C | I | I |
| Architecture Vision | A/R | R | C | C | I | I | C | C | I | I |
| Stakeholder Matrix | C | A/R | I | I | I | I | I | I | I | I |
| ARB Vision Review | A/R | R | C | I | I | I | C | C | I | I |
| **Phase 1: Requirements** | | | | | | | | | | |
| BRD | C | A/R | C | C | I | I | C | C | I | I |
| Use Case Specification | C | A | R | C | I | I | I | C | I | I |
| Product Backlog | C | A | I | R | R | R | I | I | I | I |
| **Phase 2: Architecture** | | | | | | | | | | |
| SAD | A/R | I | I | C | C | I | C | I | C | I |
| DAD | A | C | I | R | C | I | C | C | C | I |
| ADRs | A/R | I | I | C | C | C | C | I | C | I |
| Security Architecture Review | C | I | I | I | I | I | A/R | C | C | I |
| **Phase 3: Development** | | | | | | | | | | |
| Model Design and Training | C | I | I | A/R | R | I | I | I | I | I |
| Data Pipeline | C | I | I | C | R | R | I | I | I | I |
| Inference API | C | I | I | C | C | A/R | C | I | I | I |
| CI/CD Pipelines | C | I | I | I | A/R | R | C | I | C | I |
| Test Strategy | C | I | I | C | C | A/R | C | I | I | I |
| **Phase 4: Deployment** | | | | | | | | | | |
| Production Deployment | C | I | I | I | A/R | R | C | I | R | C |
| Security and Compliance Docs | C | I | I | I | I | I | A/R | R | I | I |
| Operations Runbook | C | I | I | I | C | I | C | C | C | A/R |
| Release Readiness Review | C | R | C | I | R | I | R | R | R | A |
| **Phase 5: Operations** | | | | | | | | | | |
| Monitoring and Alerts | C | I | I | C | A/R | I | C | I | R | R |
| Model Governance Review | C | I | I | A/R | R | I | I | C | I | I |
| Incident Management | C | I | I | I | R | R | C | I | R | A/R |
| Compliance Audit | C | I | C | I | I | I | R | A/R | I | C |

---

## 3. Engagement Strategy

| Stakeholder Group | Engagement Method | Frequency |
|---|---|---|
| Business Sponsor | Steering group updates, escalations | Monthly |
| ARB Members | Phase gate reviews, ADR sign-off | Per gate |
| Development Team | Sprint ceremonies, Slack/Teams | Daily |
| Security Lead | Architecture reviews, release sign-off | Per phase + on-demand |
| Compliance Lead | Requirements workshops, audit reviews | Per phase + quarterly |
| Operations Lead | Runbook walkthroughs, on-call handover | Phase 4 onwards |
| Competition Organisers | Submission portal, forum monitoring | As per competition schedule |

---

## 4. Communication Plan

| Communication | Audience | Owner | Channel | Frequency |
|---|---|---|---|---|
| Sprint Review demo | All stakeholders | Project Manager | Video call | Bi-weekly |
| Status report | Business Sponsor | Project Manager | Email | Weekly |
| Architecture decision | ARB | AI Architect | Document + meeting | Per ADR |
| Incident notification | Ops + Sponsor | Incident Commander | Email + Slack | On incident |
| Release announcement | All stakeholders | Project Manager | Email | Per release |
| Audit evidence pack | Compliance Lead | Security Lead | Secure share | Quarterly |

---

## 5. Revision History

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0 | 2026-06-30 | Praveen Mittal | Initial draft |
