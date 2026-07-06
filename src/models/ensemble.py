import torch
import torch.nn as nn
import torch.nn.functional as F
from src.models.baseline import ARGUSBackbone


class ARGUSEnsemble(nn.Module):
    """
    Ensemble model combining EfficientNet-B4, ConvNeXt-V2-Base, and EVA-02-Large backbones.
    Uses learnable softmax-normalized aggregation weights over outputs.
    Automatically handles internal input resizing dynamically.
    """

    def __init__(self, pretrained: bool = False, freeze_backbones: bool = False):
        super().__init__()
        # Instantiate model backbones
        self.backbone_effnet = ARGUSBackbone(
            model_name="efficientnet_b4", pretrained=pretrained
        )
        self.backbone_convnext = ARGUSBackbone(
            model_name="convnextv2_base", pretrained=pretrained
        )
        self.backbone_eva = ARGUSBackbone(
            model_name="eva02_large_patch14_448", pretrained=pretrained
        )

        # Softmax aggregation weights (initialized to equal 0.0, yielding equal weights under softmax)
        self.weights = nn.Parameter(torch.zeros(3))

        if freeze_backbones:
            for p in self.backbone_effnet.parameters():
                p.requires_grad = False
            for p in self.backbone_convnext.parameters():
                p.requires_grad = False
            for p in self.backbone_eva.parameters():
                p.requires_grad = False

    def forward(self, x):
        # Dynamically scale spatial input dimensions to fit model-specific sizes
        x_eva = (
            F.interpolate(x, size=(448, 448), mode="bilinear", align_corners=False)
            if x.shape[-2:] != (448, 448)
            else x
        )
        x_convnext = (
            F.interpolate(x, size=(384, 384), mode="bilinear", align_corners=False)
            if x.shape[-2:] != (384, 384)
            else x
        )
        x_effnet = (
            F.interpolate(x, size=(380, 380), mode="bilinear", align_corners=False)
            if x.shape[-2:] != (380, 380)
            else x
        )

        # Forward pass through each backbone
        out_effnet = self.backbone_effnet(x_effnet)
        out_convnext = self.backbone_convnext(x_convnext)
        out_eva = self.backbone_eva(x_eva)

        # Softmax-normalized combination weights
        alpha = F.softmax(self.weights, dim=0)

        # Aggregate logits
        logit = (
            alpha[0] * out_effnet["logit"]
            + alpha[1] * out_convnext["logit"]
            + alpha[2] * out_eva["logit"]
        )

        return {
            "logit": logit,
            "weights": alpha,
            "logits_individual": torch.stack(
                [out_effnet["logit"], out_convnext["logit"], out_eva["logit"]], dim=1
            ),
        }
