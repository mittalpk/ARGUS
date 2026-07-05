import pytest
import torch
from src.models.baseline import ARGUSBackbone
from src.training.train import profile_p95_latency

def test_argus_backbone_convnext():
    # Load backbone with convnextv2_base
    # Set pretrained=False for quick unit test execution without downloads
    model = ARGUSBackbone(model_name="convnextv2_base", pretrained=False)
    x = torch.randn(2, 3, 224, 224)
    out = model(x)
    
    assert "logit" in out
    assert "features" in out
    assert out["logit"].shape == (2,)

def test_argus_backbone_eva():
    # Load backbone with eva02_large_patch14_448
    model = ARGUSBackbone(model_name="eva02_large_patch14_448", pretrained=False)
    x = torch.randn(2, 3, 448, 448)
    out = model(x)
    
    assert "logit" in out
    assert "features" in out
    assert out["logit"].shape == (2,)

def test_profile_p95_latency():
    model = ARGUSBackbone(model_name="convnextv2_base", pretrained=False)
    device = torch.device("cpu")
    model.to(device)
    
    # Profile over 5 runs for rapid unit testing
    p95 = profile_p95_latency(model, device, image_size=64, runs=5)
    assert isinstance(p95, float)
    assert p95 > 0.0
