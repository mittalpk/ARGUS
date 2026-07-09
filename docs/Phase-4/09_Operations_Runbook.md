# ARGUS: Operations Runbook
## Production Operations, Incident Management, and On-Call Handbook

## Document Control

| Field | Detail |
|---|---|
| **Document ID** | 09_Operations_Runbook |
| **Version** | 1.0 |
| **Status** | Draft |
| **Author** | Praveen Mittal |
| **Reviewer** | Operations Lead, MLOps Engineer, Security Lead |
| **Date Created** | 2026-07-01 |
| **Last Updated** | 2026-07-01 |
| **Related Docs** | [04_SAD.md](../Phase-2/04_SAD.md), [08_Security_Compliance.md](08_Security_Compliance.md), [project_runbook.md](../project_runbook.md) |

---

> **Scope note**: this runbook describes target production operations for a
> continuously-served ARGUS API (Kubernetes, PagerDuty, Grafana dashboards,
> on-call rotation). The FREUID Challenge 2026 submission itself is a single
> offline, no-network Docker batch-inference container (see repository-root
> `Dockerfile`) — none of the always-on infrastructure below is deployed as
> part of this repository. Treat this as forward-looking design
> documentation, not a description of a currently running service.

## 1. Service Overview

| Attribute | Detail |
|---|---|
| **Service Name** | ARGUS Inference API |
| **Description** | Identity document fraud detection REST API |
| **Base URL (production)** | `https://api.argus.internal/v1` |
| **SLO — Availability** | ≥ 99.5% uptime (measured monthly) |
| **SLO — Latency** | p95 < 800 ms per inference request |
| **SLO — Error Rate** | < 1% HTTP 5xx over any 5-minute window |
| **Deployment Model** | Blue-green on Kubernetes |
| **On-Call Rotation** | https://pagerduty.argus.internal/teams/ops |
| **Escalation Contact** | Operations Lead (ops@argus.internal) |

---

## 2. On-Call Contacts

| Role | Name | Contact | Hours |
|---|---|---|---|
| Primary On-Call | Primary On-Call (rotating) | PagerDuty Alert | 24/7 rotation |
| Secondary On-Call | Secondary On-Call (rotating) | PagerDuty Alert | 24/7 rotation |
| Operations Lead | Operations Lead | ops@argus.internal | Business hours + Sev 1 |
| Security Lead | Security Lead | security@argus.internal | Business hours + data/security incidents |
| AI Solution Architect | Praveen Mittal | praveen.mittal@argus.internal | Business hours + Sev 1 |
| Infrastructure Lead | Infrastructure Lead | infra@argus.internal | Business hours + Sev 1 |

---

## 3. System Architecture Reference

```
Internet ──▶ [API Gateway / NGINX — TLS] ──▶ [Kubernetes Ingress]
                                                       │
                                          ┌────────────▼────────────┐
                                          │  FastAPI Service Pods   │
                                          │  (Blue or Green)        │
                                          └────────────┬────────────┘
                                                       │
                              ┌────────────────────────┼────────────────────┐
                              │                        │                    │
                    ┌─────────▼──────┐    ┌────────────▼──────┐   ┌────────▼──────┐
                    │ Model Registry │    │  Audit Log Sink   │   │  Prometheus   │
                    │  (MLflow)      │    │  (Immutable)      │   │  + Grafana    │
                    └────────────────┘    └───────────────────┘   └───────────────┘
```

**Namespaces**:
- `argus-production` — live inference service
- `argus-staging` — staging environment
- `argus-monitoring` — Prometheus, Grafana, Alertmanager

---

## 4. Monitoring and Dashboards

### 4.1 Grafana Dashboards

| Dashboard | URL | Purpose |
|---|---|---|
| ARGUS Service Health | https://grafana.argus.internal/d/argus-health | API latency, error rate, throughput, pod health |
| ARGUS Model Performance | https://grafana.argus.internal/d/argus-model | Fraud score distribution, confidence distribution, drift score |
| ARGUS Infrastructure | https://grafana.argus.internal/d/argus-infra | CPU, memory, GPU utilisation, pod restarts |
| ARGUS Audit | https://grafana.argus.internal/d/argus-audit | Request volume, human review rate, classification breakdown |

### 4.2 Key Metrics to Monitor

**Service Metrics (Prometheus)**:

| Metric | Normal Range | Alert Threshold |
|---|---|---|
| `argus_request_latency_p95_ms` | < 500 ms | > 800 ms for 5 min |
| `argus_http_error_rate_5xx` | < 0.2% | > 1% for 5 min |
| `argus_requests_per_minute` | 10–150 | < 1 for 10 min (dead traffic alert) |
| `argus_pod_restarts_total` | 0 | > 3 in 10 min |
| `argus_model_load_time_seconds` | < 30 s | > 60 s on startup |

**Model Metrics**:

| Metric | Normal Range | Alert Threshold |
|---|---|---|
| `argus_fraud_score_mean` | 0.2–0.8 (depends on traffic mix) | Drift > 2 std deviations for 3 windows |
| `argus_confidence_mean` | > 0.75 | < 0.65 sustained for 1 hour |
| `argus_human_review_rate` | < 15% | > 30% for 1 hour |
| `argus_drift_score` | < 0.05 | > 0.10 for 3 consecutive daily checks |

**Infrastructure Metrics**:

| Metric | Normal Range | Alert Threshold |
|---|---|---|
| CPU utilisation (per pod) | < 60% | > 85% for 15 min |
| Memory utilisation (per pod) | < 70% | > 85% for 15 min |
| GPU memory (inference workers) | < 80% | > 90% for 5 min |
| PVC storage utilisation | < 70% | > 85% |

### 4.3 Log Access

```bash
# Tail live inference logs (production)
kubectl logs -n argus-production -l app=argus-api --follow

# Query audit logs in CloudWatch
aws logs filter-log-events   --log-group-name /argus/production/audit   --start-time $(date -d '1 hour ago' +%s000)   --filter-pattern "{ $.result = "fraud" }"

# Check pod status
kubectl get pods -n argus-production

# Describe a specific pod
kubectl describe pod <pod-name> -n argus-production
```

---

## 5. Deployment Procedures

### 5.1 Standard Release — Blue-Green Deployment

**Pre-conditions**:
- Release candidate approved in GitHub Actions
- All CI/CD gates passing
- Go/No-Go approval received from Release Readiness Review
- On-call engineer notified

**Step-by-step**:

```
Step 1: Confirm current state
──────────────────────────────
kubectl get svc argus-api -n argus-production -o jsonpath='{.spec.selector}'
# Confirm traffic is currently on blue deployment

Step 2: Deploy green environment
──────────────────────────────
helm upgrade --install argus-green ./helm/argus   --namespace argus-production   --set image.tag=<RELEASE_TAG>   --set deployment.name=argus-green   --values helm/values-production.yaml

Step 3: Monitor green startup
──────────────────────────────
kubectl rollout status deployment/argus-green -n argus-production
# Wait for all pods READY

Step 4: Run smoke tests on green (no user traffic)
──────────────────────────────
kubectl port-forward svc/argus-green-internal 8080:8000 -n argus-production &
curl http://localhost:8080/v1/health
curl http://localhost:8080/v1/ready
python scripts/smoke_test.py --base-url http://localhost:8080
# All checks must pass before proceeding

Step 5: Route 5% canary traffic to green
──────────────────────────────
kubectl apply -f helm/canary-5pct.yaml
# Monitor Grafana for 10 minutes — latency, error rate, fraud score distribution

Step 6: Progressive traffic increase
──────────────────────────────
# If Step 5 stable: increase to 25%
kubectl apply -f helm/canary-25pct.yaml
# Monitor 10 min

# If Step 6 stable: increase to 50%
kubectl apply -f helm/canary-50pct.yaml
# Monitor 10 min

# If stable: full cutover to green
kubectl apply -f helm/canary-100pct.yaml

Step 7: Confirm full cutover
──────────────────────────────
kubectl get svc argus-api -n argus-production -o jsonpath='{.spec.selector}'
# Selector should now point to argus-green

Step 8: Monitor post-release (30 minutes)
──────────────────────────────
# Watch Grafana Service Health dashboard
# Confirm all metrics within normal range

Step 9: Close release
──────────────────────────────
# Update release notes with deployment confirmation
# Set release closure window end time (blue retained for 24 hours)
# Notify stakeholders
```

### 5.2 Hotfix Release

Hotfixes follow the same procedure with the following differences:
- Expedited Go/No-Go: Security Lead + Operations Lead approval only (no full board)
- Smoke test window reduced to 5 minutes
- Canary traffic step skipped for Sev 1 hotfixes — direct full cutover after smoke tests
- Post-release monitoring window extended to 60 minutes

### 5.3 Scaling Operations

```bash
# Manual scale-out (if HPA insufficient)
kubectl scale deployment argus-green -n argus-production --replicas=10

# Check HPA status
kubectl get hpa -n argus-production

# Update HPA max replicas
kubectl patch hpa argus-hpa -n argus-production   -p '{"spec":{"maxReplicas":20}}'
```

---

## 6. Rollback Procedures

### 6.1 Rollback Triggers

Immediate rollback is required when any of the following occur:

- Sev 1 incident declared during or after release
- p95 latency > 1600 ms (2× SLO) for 15 minutes
- HTTP 5xx error rate > 5% for 10 minutes
- Fraud score distribution shift > 3 standard deviations from baseline
- Critical security control failure or authentication anomaly
- On-call engineer judgement call — no approval needed for Sev 1

### 6.2 Rollback Steps

```
Step 1: Declare rollback — notify #argus-ops channel
──────────────────────────────
# Time: T+0

Step 2: Switch all traffic back to blue
──────────────────────────────
kubectl apply -f helm/canary-0pct.yaml
# OR direct service selector patch:
kubectl patch svc argus-api -n argus-production   -p '{"spec":{"selector":{"app":"argus-blue"}}}'
# Time: T+2 min target

Step 3: Verify blue is serving correctly
──────────────────────────────
curl https://api.argus.internal/v1/health
# Check Grafana — error rate and latency should recover immediately

Step 4: Scale down green
──────────────────────────────
kubectl scale deployment argus-green -n argus-production --replicas=0

Step 5: Open incident record
──────────────────────────────
# Create incident ticket; assign incident commander
# Begin timeline capture

Step 6: Revoke release candidate from promotion path
──────────────────────────────
# Tag release in GitHub as ROLLBACK_<version>
# Mark MLflow model as REJECTED in registry

Step 7: Notify stakeholders
──────────────────────────────
# Sev 1: immediate notification to Operations Lead, Sponsor
# Send incident update within 30 minutes

Step 8: Root cause analysis
──────────────────────────────
# Complete RCA within 2 business days
# Corrective and preventive actions tracked in incident ticket
```

---

## 7. Incident Management

### 7.1 Severity Levels

| Severity | Definition | Response Start | Update Frequency | Target Resolution |
|---|---|---|---|---|
| **Sev 1** | Production outage, systemic fraud escape, critical security/compliance breach | 15 minutes | Every 30 minutes | 4 hours |
| **Sev 2** | Major API degradation, SLO breach with business impact, significant model performance drop | 30 minutes | Every 60 minutes | 8 hours |
| **Sev 3** | Partial degradation, elevated error rate below SLO, non-critical feature impact | 4 hours | Daily | 3 business days |
| **Sev 4** | Low-impact issue, cosmetic, documentation, minor enhancement | Next business day | Weekly | Planned sprint |

### 7.2 Incident Roles

| Role | Responsibility |
|---|---|
| **Incident Commander** | Owns the incident end-to-end; coordinates response; makes calls; communicates status |
| **Technical Lead** | Drives diagnosis and remediation; proposes mitigations |
| **Communications Lead** | Stakeholder and executive updates; status page management |
| **Scribe** | Real-time timeline capture; action log; decision record |
| **Security Lead** | Required for data incidents, fraud escapes, or compliance breaches |

### 7.3 Incident Response Workflow

```
Alert Fires / Human Reports Incident
              │
              ▼
    Classify Severity (on-call engineer)
              │
     ┌────────┴─────────┐
   Sev 1/2            Sev 3/4
     │                   │
     ▼                   ▼
Page IC + Team      Assign owner
Declare incident    Schedule fix
     │
     ▼
Assemble response team (bridge call)
     │
     ▼
Diagnose and mitigate impact
(rollback if deployment-related)
     │
     ▼
Communicate status (30 min cadence for Sev 1)
     │
     ▼
Resolve and verify service recovery
     │
     ▼
Close incident; schedule post-incident review
     │
     ▼
Post-Incident Review (within 2 business days)
     │
     ▼
Corrective and preventive actions → sprint backlog
```

### 7.4 Incident Communication Templates

**Sev 1 — Initial Notification**:
```
INCIDENT DECLARED — ARGUS [Sev 1]
Time: [HH:MM] CEST
Impact: [Description of impact]
Status: Investigating
IC: [Incident Commander Role]
Next update: [HH:MM + 30 min]
```

**Sev 1 — Update**:
```
INCIDENT UPDATE — ARGUS [Sev 1]
Time: [HH:MM] CEST
Status: [Investigating / Mitigating / Monitoring / Resolved]
Current impact: [Description]
Actions taken: [Summary]
Next update: [HH:MM + 30 min]
```

**Incident Resolved**:
```
INCIDENT RESOLVED — ARGUS [Sev N]
Time resolved: [HH:MM] CEST
Duration: [X hours Y minutes]
Root cause (preliminary): [Summary]
Full RCA: [YYYY-MM-DD]
```

### 7.5 Common Incident Runbooks

#### RK-01: High API Latency

```
1. Check Grafana — argus_request_latency_p95_ms
2. Check pod CPU and memory — kubectl top pods -n argus-production
3. Check GPU memory — nvidia-smi on inference nodes
4. Check if recent deployment — if yes, consider rollback (Section 6)
5. Scale out pods if resource-constrained:
   kubectl scale deployment argus-green -n argus-production --replicas=N
6. Check for upstream dependency issues (MLflow, object store)
7. If unresolved in 30 min and p95 > 2× SLO — escalate to Sev 1
```

#### RK-02: High Error Rate

```
1. Check Grafana error rate dashboard — identify error type (4xx vs 5xx)
2. kubectl logs -n argus-production -l app=argus-api --tail=200
3. Check for OOM kills: kubectl describe pods -n argus-production | grep OOMKilled
4. Check for model loading failures: grep "model_load" in pod logs
5. If 5xx > 5% for 10 min — trigger rollback (Section 6)
6. If 4xx spike — check for upstream client changes or API gateway misconfiguration
```

#### RK-03: Pod Crash Loop

```
1. kubectl get pods -n argus-production
2. kubectl describe pod <pod-name> -n argus-production
3. kubectl logs <pod-name> -n argus-production --previous
4. Common causes:
   - OOM: increase memory limit in helm values
   - Model load failure: check MLflow model registry; verify artifact accessibility
   - Secrets unavailable: check Vault / Secrets Manager connectivity
5. If > 3 pods crash-looping — declare Sev 1; trigger rollback
```

#### RK-04: Model Drift Alert

```
1. Check Grafana model performance dashboard
2. Review argus_drift_score metric — confirm sustained breach (not transient)
3. Review fraud_score distribution plot — compare to baseline
4. Check if input data characteristics have shifted (new document types?)
5. Consult Lead Data Scientist
6. Decision tree:
   - Transient spike → monitor; no action
   - Sustained drift < 0.15 → schedule retraining; log in improvement backlog
   - Sustained drift > 0.15 or fraud escape suspected → Sev 2; emergency retraining
```

#### RK-05: Security Alert — Secret Exposure

```
1. Immediately revoke the exposed credential
2. Audit access logs for any usage of the exposed credential
3. Declare Sev 1 if production access was possible
4. Notify Security Lead immediately
5. Rotate all credentials in the same scope as a precaution
6. Conduct post-incident review within 24 hours
7. Update secret scanning configuration to prevent recurrence
```

---

## 8. Model Governance Operations

### 8.1 Champion-Challenger Promotion Workflow

```
1. Candidate model registered in MLflow with status: STAGING
2. Lead Data Scientist runs champion vs challenger evaluation report
3. Report reviewed in monthly Model Governance Review
4. If challenger outperforms champion on all acceptance criteria:
   a. Update model status to APPROVED in MLflow
   b. Create release candidate PR with new model version
   c. CI/CD model gate validates metrics
   d. Release proceeds through standard deployment procedure
5. If challenger does not outperform: status set to ARCHIVED; reason logged
```

### 8.2 Emergency Model Replacement

Triggered when:
- Sev 1 fraud escape confirmed
- Critical model vulnerability discovered
- Regulatory directive requires immediate model change

```
1. Declare Sev 1 incident
2. Roll back to previous champion (Section 6.2)
3. Assess whether rollback model is safe to operate
4. If no safe model available: take service offline; activate manual review process
5. Fast-track challenger evaluation (48-hour turnaround)
6. Deploy replacement via hotfix procedure (Section 5.2)
```

---

## 9. Continuous Improvement and Retraining

### 9.1 Scheduled Reviews

| Review | Frequency | Owner | Output |
|---|---|---|---|
| Model Performance Review | Monthly | Lead Data Scientist | Performance report; retraining decision |
| Drift Report | Weekly automated | MLOps Engineer | Drift score; alert if threshold exceeded |
| Operations Review | Weekly | Operations Lead | SLO status; incident review; action items |
| Capacity Review | Monthly | Infrastructure Lead | Scaling decisions; cost review |
| Compliance Review | Quarterly | Compliance Lead | Evidence review; gap assessment |

### 9.2 Retraining Decision Criteria

| Trigger | Action |
|---|---|
| Drift score > 0.10 for 3 consecutive daily checks | Schedule retraining in next sprint |
| False positives increase > 15% over baseline for 7 days | Prioritise retraining; review threshold |
| False negatives increase > 10% over baseline for 7 days | Sev 2; emergency retraining review |
| New dominant attack pattern identified | Architecture review; targeted data collection |
| Competition dataset updated with new samples | Plan retraining sprint |

### 9.3 Retraining Workflow

```
1. Trigger logged in improvement backlog with rationale
2. Data Engineer confirms updated/new dataset available
3. Lead Data Scientist trains challenger model following ML Design doc
4. Challenger evaluated against champion (Section 8.1)
5. If challenger approved: deploy via standard release
6. Retraining decision and outcome logged in MLflow and compliance evidence
```

---

## 10. Capacity and Cost Management

### 10.1 Kubernetes Resource Allocation

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit | GPU |
|---|---|---|---|---|---|
| API Pod | 1 core | 4 cores | 2 Gi | 8 Gi | None |
| Inference Worker (EVA-02) | 2 cores | 8 cores | 8 Gi | 16 Gi | 1× A100 (or equiv) |
| Inference Worker (EfficientNet-B4) | 1 core | 4 cores | 4 Gi | 8 Gi | Optional GPU |
| MLflow Server | 1 core | 2 cores | 2 Gi | 4 Gi | None |
| Prometheus | 1 core | 2 cores | 2 Gi | 4 Gi | None |

### 10.2 HPA Configuration

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: argus-hpa
  namespace: argus-production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: argus-green
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
  - type: Pods
    pods:
      metric:
        name: argus_request_latency_p95_ms
      target:
        type: AverageValue
        averageValue: "500"
```

### 10.3 Cost Alerts

| Alert | Threshold | Action |
|---|---|---|
| Daily GPU compute spend | > $500 | Notify Infrastructure Lead |
| Monthly total cloud spend | > $10,000 | Notify Project Manager + Sponsor |
| Storage growth rate | > 20% month-on-month | Review retention policy |

---

## 11. Backup and Recovery

| Asset | Backup Method | Frequency | Retention | Recovery Procedure |
|---|---|---|---|---|
| MLflow model artifacts | Object store versioning + cross-region replication | Continuous | 3 years | Restore from S3/GCS version |
| MLflow experiment database | Managed DB snapshot | Daily | 90 days | Restore from snapshot |
| Audit log store | Immutable + cross-region replication | Continuous | 5 years | Read from replica |
| Kubernetes manifests | Git repository | On every change | Indefinite | Re-apply from git |
| Helm values | Git repository | On every change | Indefinite | Re-apply from git |
| Prometheus metrics | Remote write to long-term store | Continuous | 13 months | Query long-term store |

---

## 12. Service Runbook — Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│           ARGUS ON-CALL QUICK REFERENCE                     │
├─────────────────────────────────────────────────────────────┤
│ Health check:                                               │
│   curl https://api.argus.internal/v1/health                 │
│                                                             │
│ Check pods:                                                 │
│   kubectl get pods -n argus-production                      │
│                                                             │
│ Tail logs:                                                  │
│   kubectl logs -n argus-production -l app=argus-api -f      │
│                                                             │
│ Scale up:                                                   │
│   kubectl scale deployment argus-green \                    │
│     -n argus-production --replicas=N                        │
│                                                             │
│ ROLLBACK (emergency):                                       │
│   kubectl patch svc argus-api -n argus-production \         │
│     -p '{"spec":{"selector":{"app":"argus-blue"}}}'         │
│                                                             │
│ Grafana: https://grafana.argus.internal    PagerDuty: https://pagerduty.argus.internal    Runbook: 09_Operations_Runbook.md │
└─────────────────────────────────────────────────────────────┘
```

---

## 13. Operational Handover Checklist

Complete before operational ownership transfers from the project team to the operations team:

- [ ] On-call roster published and PagerDuty rotation configured
- [ ] All Grafana dashboards reviewed and approved by operations team
- [ ] All alert thresholds reviewed and approved
- [ ] Rollback procedure walked through in staging with operations team
- [ ] All incident runbooks (RK-01 to RK-05) reviewed
- [ ] Access provisioned for operations team (Kubernetes, Grafana, MLflow, audit logs)
- [ ] Escalation contacts confirmed and tested
- [ ] Backup and recovery procedures verified
- [ ] Operations team completed one full deployment exercise in staging
- [ ] Model Governance Review schedule confirmed
- [ ] Operations documentation reviewed and signed off

---

## 14. Sign-Off

| Praveen Mittal | AI Solution Architect | Approved | 2026-07-02 |
| Operations Lead | Operations Lead | Approved | 2026-07-02 |
| MLOps Engineer | MLOps Engineer | Approved | 2026-07-02 |
| Security Lead | Security Lead | Approved | 2026-07-02 |
