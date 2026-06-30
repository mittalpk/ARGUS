# ADR-002: FastAPI as Inference API Framework

## Document Control

| Field | Detail |
|---|---|
| **ADR ID** | ADR-002 |
| **Title** | FastAPI as Inference API Framework |
| **Status** | Accepted |
| **Author** | Praveen Mittal |
| **Date** | 2026-06-30 |
| **Deciders** | AI Solution Architect, ARB |

---

## Context

The inference service must expose a REST API with low latency, async support, automatic OpenAPI documentation, and production-grade reliability.

---

### Options Considered

| Option | Pros | Cons |
|---|---|---|
| **FastAPI** | Async-native; OpenAPI auto-generated; Pydantic validation; high performance; widely adopted in ML serving | Requires Uvicorn/Gunicorn for production serving |
| Flask | Simple; well-known | Synchronous by default; no built-in schema validation; lower throughput |
| Django REST Framework | Full-featured | Heavy; overkill for a single inference service |
| Triton Inference Server | Optimised for GPU serving | Complex ops; limited Python flexibility |

### Decision

**FastAPI** with **Uvicorn** (ASGI server) and **Gunicorn** as the process manager.

### Rationale

- Async support allows concurrent inference requests without blocking
- Pydantic models enforce request/response schema contracts automatically
- OpenAPI docs at `/docs` satisfy FR-14 with zero additional code
- Lightweight and easy to containerise

### Consequences

- **Positive**: Low-boilerplate API with built-in validation; async throughput; auto-documentation
- **Negative**: Less opinionated than Django — team must manage middleware and auth explicitly
- **Neutral**: Standard production pattern: Gunicorn (process manager) → Uvicorn (ASGI worker)

---

## Status

**Accepted**

---

## References

- [04_SAD.md](../04_SAD.md)
- [02_BRD.md](../../Phase-1/02_BRD.md)
- [01_Architecture_Vision.md](../../Phase-0/01_Architecture_Vision.md)
