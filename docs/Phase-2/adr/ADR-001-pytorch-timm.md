# ADR-001: PyTorch + timm as ML Framework

## Document Control

| Field | Detail |
|---|---|
| **ADR ID** | ADR-001 |
| **Title** | PyTorch + timm as ML Framework |
| **Status** | Accepted |
| **Author** | Praveen Mittal |
| **Date** | 2026-06-30 |
| **Deciders** | AI Solution Architect, ARB |

---

## Context

The project requires a deep learning framework capable of supporting multiple large vision backbones (EVA-02-Large, ConvNeXt-V2-Base, EfficientNet-B4), experiment reproducibility, and active community support.

---

### Options Considered

| Option | Pros | Cons |
|---|---|---|
| **PyTorch + timm** | Widest backbone ecosystem; timm has all three required models; strong research and production community; native ONNX export | Requires more boilerplate than high-level wrappers |
| TensorFlow / Keras | Mature production tooling | EVA-02-Large not well supported; migration overhead |
| JAX / Flax | Excellent performance on TPU | Smaller ecosystem; team unfamiliar; limited timm support |
| PyTorch Lightning only | Reduces boilerplate | Adds abstraction layer; not required given team size |

### Decision

**PyTorch** (latest stable) as the core deep learning framework with **timm** (latest stable) as the backbone library.

### Rationale

- EVA-02-Large, ConvNeXt-V2-Base, and EfficientNet-B4 are all available in timm with pretrained weights
- PyTorch is the dominant framework in academic fraud detection research, ensuring alignment with the competition community
- Native support for custom training loops, loss functions, and mixed-precision training
- Strong ONNX export path for future production optimisation

### Consequences

- **Positive**: Rapid backbone experimentation; pretrained weights readily available; large support community
- **Negative**: More manual boilerplate than Keras; team must manage training loop explicitly
- **Neutral**: Hydra + MLflow integration well-documented for PyTorch

---

## Status

**Accepted**

---

## References

- [04_SAD.md](../04_SAD.md)
- [02_BRD.md](../../Phase-1/02_BRD.md)
- [01_Architecture_Vision.md](../../Phase-0/01_Architecture_Vision.md)
