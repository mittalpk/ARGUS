import torch
from src.models.ensemble import ARGUSEnsemble


def test_ensemble_initialization():
    model = ARGUSEnsemble(pretrained=False, freeze_backbones=False)

    assert hasattr(model, "backbone_effnet")
    assert hasattr(model, "backbone_convnext")
    assert hasattr(model, "backbone_eva")
    assert isinstance(model.weights, torch.nn.Parameter)
    assert model.weights.shape == (3,)
    assert model.weights.requires_grad is True


def test_ensemble_forward_pass():
    model = ARGUSEnsemble(pretrained=False, freeze_backbones=False)
    x = torch.randn(2, 3, 448, 448)

    out = model(x)
    assert "logit" in out
    assert "weights" in out
    assert "logits_individual" in out

    assert out["logit"].shape == (2,)
    assert out["weights"].shape == (3,)
    assert out["logits_individual"].shape == (2, 3)

    # Softmax weights should sum to 1.0
    assert torch.allclose(out["weights"].sum(), torch.tensor(1.0))


def test_ensemble_freeze_parameters():
    # Instantiate with freeze_backbones=True
    model = ARGUSEnsemble(pretrained=False, freeze_backbones=True)

    # Backbone parameters should have requires_grad set to False
    for p in model.backbone_effnet.parameters():
        assert p.requires_grad is False
    for p in model.backbone_convnext.parameters():
        assert p.requires_grad is False
    for p in model.backbone_eva.parameters():
        assert p.requires_grad is False

    # Combination weights must still require gradients
    assert model.weights.requires_grad is True


def test_ensemble_interpolation():
    model = ARGUSEnsemble(pretrained=False, freeze_backbones=False)
    # Test dynamic spatial resizing on smaller non-standard resolution input
    x = torch.randn(1, 3, 128, 128)

    out = model(x)
    assert out["logit"].shape == (1,)
