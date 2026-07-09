import os
import glob
import logging
import pandas as pd
import torch
import albumentations as A
from albumentations.pytorch import ToTensorV2
from PIL import Image
from src.models.baseline import ARGUSBackbone

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# The champion checkpoint promoted by scripts/check_model_gate.py, baked into
# the Docker image (see Dockerfile). EfficientNet-B4 is the shipped default
# because it is the lightweight, lower-latency backbone (see README) that is
# tractable to train end-to-end within the reproducibility environment; the
# ensemble architecture remains available via --model_name ensemble for teams
# with the compute budget to train all three backbones.
DEFAULT_CHECKPOINT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "checkpoints",
    "champion_efficientnet_b4.pth",
)


def predict_labels(
    input_dir: str = "/data",
    output_csv: str = "/submissions/submission.csv",
    model_name: str = "efficientnet_b4",
    checkpoint_path: str = DEFAULT_CHECKPOINT_PATH,
):
    """
    Reads flat test images from input_dir, runs inference, and writes predictions to output_csv.
    """
    logger.info(f"Scanning for images in {input_dir}...")

    # Supported image extensions per challenge reproducibility requirements
    extensions = ("*.jpeg", "*.jpg", "*.png", "*.webp", "*.bmp", "*.tif", "*.tiff")
    image_paths = []
    for ext in extensions:
        # Scan case-insensitive
        image_paths.extend(glob.glob(os.path.join(input_dir, ext)))
        image_paths.extend(glob.glob(os.path.join(input_dir, ext.upper())))

    image_paths = sorted(list(set(image_paths)))
    logger.info(f"Found {len(image_paths)} images to process.")

    # Initialize the model backbone
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        try:
            # torch.cuda.is_available() only checks that a CUDA driver and
            # device are present, not that this torch build actually ships
            # kernels for the device's compute capability. Probe with a real
            # kernel launch so unsupported GPUs (e.g. a PyTorch build without
            # sm_120 support on a Blackwell-class card) fall back to CPU
            # instead of silently failing every forward pass and defaulting
            # every prediction to 0.5 (see the except branch in the loop below).
            test_tensor = torch.randn(1, 3, 32, 32).to(device)
            test_layer = torch.nn.Conv2d(3, 3, 3).to(device)
            test_layer(test_tensor)
        except Exception as e:
            logger.warning(
                f"CUDA is available but incompatible with this PyTorch build: {e}"
            )
            logger.warning("Falling back to CPU mode.")
            device = torch.device("cpu")
    logger.info(f"Using inference device: {device}")

    # Pretrained=False to comply with no-network sandbox requirements
    if model_name.lower() == "ensemble":
        from src.models.ensemble import ARGUSEnsemble

        model = ARGUSEnsemble(pretrained=False)
    else:
        model = ARGUSBackbone(model_name=model_name, pretrained=False)

    # Load model weights if provided
    if checkpoint_path and os.path.exists(checkpoint_path):
        logger.info(f"Loading model checkpoint from {checkpoint_path}...")
        model.load_state_dict(
            torch.load(checkpoint_path, map_location=device, weights_only=True)
        )
    else:
        logger.warning(
            "No valid checkpoint path provided. Running inference with randomly initialized weights (Liveness verification mode)."
        )

    model.to(device)
    model.eval()

    # Match the image size required by the model architecture
    if model_name.lower() == "ensemble":
        image_size = 448
    else:
        image_size = (
            448 if "eva" in model_name else (384 if "convnext" in model_name else 380)
        )

    # Validation/Inference transform
    transform = A.Compose(
        [
            A.Resize(image_size, image_size),
            A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
            ToTensorV2(),
        ]
    )

    records = []

    with torch.no_grad():
        for path in image_paths:
            filename = os.path.basename(path)
            # Row ID is the filename without extension
            row_id, _ = os.path.splitext(filename)

            try:
                # Load image safely
                with Image.open(path) as img:
                    img_conv = img.convert("RGB")
                    # Convert PIL to numpy array for Albumentations
                    import numpy as np

                    img_np = np.array(img_conv)

                # Apply transforms
                transformed = transform(image=img_np)
                tensor_input = transformed["image"].unsqueeze(0).to(device)

                # Forward pass
                outputs = model(tensor_input)
                prob = torch.sigmoid(outputs["logit"]).item()

                records.append({"id": row_id, "label": prob})
            except Exception as e:
                logger.error(f"Failed to process image {filename}: {e}")
                # Append 0.5 default on error to guarantee prediction row alignment
                records.append({"id": row_id, "label": 0.5})

    # Write submission file matching requested schema
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df = pd.DataFrame(records)

    # Enforce correct output ordering or columns
    if df.empty:
        df = pd.DataFrame(columns=["id", "label"])

    df.to_csv(output_csv, index=False)
    logger.info(f"Saved submission to {output_csv}. Total predictions: {len(df)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="FREUID Challenge 2026 Submission Generator"
    )
    parser.add_argument(
        "--input_dir",
        type=str,
        default="/data",
        help="Directory containing test images",
    )
    parser.add_argument(
        "--output_csv",
        type=str,
        default="/submissions/submission.csv",
        help="Path to write submission.csv",
    )
    parser.add_argument(
        "--model_name",
        type=str,
        default="efficientnet_b4",
        help="Model backbone name",
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default=DEFAULT_CHECKPOINT_PATH,
        help="Path to trained model weights checkpoint (.pth)",
    )

    args = parser.parse_args()
    predict_labels(
        input_dir=args.input_dir,
        output_csv=args.output_csv,
        model_name=args.model_name,
        checkpoint_path=args.checkpoint,
    )
