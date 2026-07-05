import torch
import torch.nn as nn
import timm


class ARGUSBackbone(nn.Module):
    def __init__(
        self, model_name: str, pretrained: bool = True, drop_rate: float = 0.2
    ):
        super().__init__()
        # Create backbone encoder without classification head (num_classes=0)
        self.encoder = timm.create_model(
            model_name, pretrained=pretrained, num_classes=0, drop_rate=drop_rate
        )

        # Classification head matching ML Design document Section 4.1
        self.head = nn.Sequential(
            nn.Linear(self.encoder.num_features, 512),
            nn.GELU(),
            nn.Dropout(drop_rate),
            nn.Linear(512, 1),
        )

    def forward(self, x: torch.Tensor) -> dict:
        features = self.encoder(x)
        logit = self.head(features).squeeze(1)
        return {"logit": logit, "features": features}
