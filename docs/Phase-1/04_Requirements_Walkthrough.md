# ARGUS: Requirements Walkthrough & Sign-Off
## Phase 1 Gate Review Meeting

## Document Control

| Field | Detail |
|---|---|
| **Document ID** | 04_Requirements_Walkthrough |
| **Version** | 1.0 |
| **Status** | Approved |
| **Author** | Praveen Mittal |
| **Review Date** | 2026-06-30 |
| **Meeting Link** | https://meet.argus.internal/requirements-walkthrough |

---

## 1. Purpose

This document records the proceedings, decisions, and sign-offs from the **Requirements Walkthrough & Sign-Off** ceremony. This review serves as the formal gate for Phase 1 (Business & Requirements Definition). Approval of this document authorizes the project to proceed to Phase 2 (Architecture & Technical Design).

---

## 2. Attendees

| Name | Role | Present |
|---|---|---|
| Praveen Mittal | AI Solution Architect / Project Lead | Yes |
| Business Sponsor | Business Sponsor | Yes |
| Project Manager | Project Manager | Yes |
| Lead Data Scientist | Lead Data Scientist | Yes |
| Compliance Lead | Compliance Lead | Yes |
| Security Lead | Security Lead | Yes |
| Operations Lead | Operations Lead | Yes |

---

## 3. Agenda & Discussion Summary

### 3.1 Business Requirements Document (BRD) Review
*   **Discussion**: Walked through the core business objectives. Confirmed that the primary target is the FREUID Challenge 2026 leaderboard using the **APCER @ 1% BPCER** and **AuDET** metrics.
*   **Key Decision**: The target operating threshold for the production system was confirmed to prioritize minimizing false negatives (preventing fraud escapes) while maintaining acceptable customer friction.

### 3.2 Use Case & User Story Review
*   **Discussion**: Reviewed the 10 core use cases spanning classification, attack-specific detections (physical, GenAI, print-and-capture), batching, model training/deployment, and human review routing.
*   **Key Decision**: The human review queue threshold (UC-08) is provisionally set to flag any prediction with a confidence score below `0.70` or a fraud score in the ambiguous range (`0.40 - 0.60`).

### 3.3 Non-Functional & Compliance Requirements Review
*   **Discussion**: Discussed the p95 latency budget of `< 800 ms`. The team noted that using the full ensemble (specifically EVA-02-Large) might challenge this budget under peak load.
*   **Key Decision**: Approved the alternative flow where the API consumer can fall back to a single backbone (EfficientNet-B4) or return a low-latency estimate if the latency budget is breached.
*   **Compliance**: The Compliance Lead confirmed the system meets the high-risk classification requirements of the **EU AI Act**, and that EXIF stripping at ingestion satisfies the **GDPR** data minimization requirement.

---

## 4. Phase 1 Exit Checklist

| Criterion | Status | Notes |
|---|---|---|
| Business Requirements Document (BRD) completed | ✅ Confirmed | [02_BRD.md](02_BRD.md) |
| Use Case Specifications completed | ✅ Confirmed | [03_Use_Case_Specification.md](03_Use_Case_Specification.md) |
| Non-Functional Requirements (NFRs) baselined | ✅ Confirmed | Outlined in BRD Section 5 |
| Product Backlog initialized | ✅ Confirmed | User stories seeded in Use Case Spec Section 4 |
| Compliance review completed | ✅ Confirmed | EU AI Act and GDPR controls mapped |

---

## 5. Action Items

| ID | Action Item | Owner | Due Date | Status |
|---|---|---|---|---|
| AI-1.1 | Establish the model latency benchmark environment | Lead Data Scientist | Phase 2 | Open |
| AI-1.2 | Draft the initial API contract schema for UC-01 | Software Engineer | Phase 2 | Open |
| AI-1.3 | Map out detailed dataset features for the DAD | Data Engineer | Phase 2 | Open |

---

## 6. Sign-Off

By signing below, the stakeholders confirm that the Business Requirements and Use Cases are approved, and the project is authorized to proceed to **Phase 2: Architecture and Technical Design**.

| Name | Role | Decision | Signature | Date |
|---|---|---|---|---|
| Business Sponsor | Business Sponsor | Approved | | 2026-06-30 |
| Project Manager | Project Manager | Approved | | 2026-06-30 |
| Praveen Mittal | AI Solution Architect | Approved | | 2026-06-30 |
| Lead Data Scientist | Lead Data Scientist | Approved | | 2026-06-30 |
| Compliance Lead | Compliance Lead | Approved | | 2026-06-30 |
