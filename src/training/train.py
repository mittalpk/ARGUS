import os
import random
import logging
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from PIL import Image
import albumentations as A
from albumentations.pytorch import ToTensorV2
import hydra
from omegaconf import DictConfig
import mlflow
import mlflow.pytorch
from src.models.baseline import ARGUSBackbone
from src.models.ensemble import ARGUSEnsemble
from src.training.metrics import compute_apcer_at_target_bpcer, compute_audet

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


# Set random seeds for reproducibility
def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class ARGUSDataset(Dataset):
    def __init__(self, labels_csv: str, img_dir: str, transform=None):
        self.df = pd.read_csv(labels_csv)
        self.img_dir = img_dir
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img_name = row["image_id"]
        img_path = os.path.join(self.img_dir, img_name)

        # Load image safely
        img = np.array(Image.open(img_path).convert("RGB"))
        label = float(row["label"])

        if self.transform:
            augmented = self.transform(image=img)
            img = augmented["image"]

        return img, torch.tensor(label, dtype=torch.float32)


def profile_p95_latency(model, device, image_size: int, runs: int = 100) -> float:
    """
    Measures the 95th percentile inference latency in milliseconds for a batch size of 1.
    """
    import time

    model.eval()
    durations = []

    # Warm-up passes
    dummy_input = torch.randn(1, 3, image_size, image_size).to(device)
    with torch.no_grad():
        for _ in range(10):
            _ = model(dummy_input)

        # Benchmark runs
        for _ in range(runs):
            start = time.perf_counter()
            _ = model(dummy_input)
            if device.type == "cuda":
                torch.cuda.synchronize()
            durations.append((time.perf_counter() - start) * 1000.0)

    p95 = np.percentile(durations, 95)
    return float(p95)


@hydra.main(version_base=None, config_path="../../configs", config_name="config")
def main(cfg: DictConfig):
    # Cap CPU threads in constrained sandboxes (e.g. CI); leave PyTorch's
    # default alone for real training runs unless explicitly overridden.
    num_threads = cfg.training.get("num_threads", None)
    if num_threads:
        torch.set_num_threads(int(num_threads))
    set_seed(cfg.training.seed)

    # Read model-specific parameters or fallback to defaults
    image_size = cfg.model.get("image_size", cfg.data.image_size)
    use_amp = cfg.model.get("use_amp", False)

    # Configure MLflow
    mlflow.set_tracking_uri(cfg.mlflow.tracking_uri)
    mlflow.set_experiment(cfg.mlflow.experiment_name)

    # Albumentations transforms using model-specific image_size
    train_transform = A.Compose(
        [
            A.Resize(image_size, image_size),
            A.HorizontalFlip(p=0.5),
            A.RandomBrightnessContrast(p=0.2),
            A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
            ToTensorV2(),
        ]
    )

    val_transform = A.Compose(
        [
            A.Resize(image_size, image_size),
            A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
            ToTensorV2(),
        ]
    )

    # Load dataset partitions
    train_csv = os.path.join(cfg.data.splits_dir, "train_labels.csv")
    val_csv = os.path.join(cfg.data.splits_dir, "val_labels.csv")

    train_dataset = ARGUSDataset(
        train_csv, os.path.join(cfg.data.splits_dir, "train"), transform=train_transform
    )
    val_dataset = ARGUSDataset(
        val_csv, os.path.join(cfg.data.splits_dir, "val"), transform=val_transform
    )

    # Safeguard against empty dataset partitions
    if len(train_dataset) == 0 or len(val_dataset) == 0:
        raise ValueError(
            f"Dataset partition check failed. Train size: {len(train_dataset)}, "
            f"Val size: {len(val_dataset)}. Partitions must contain at least 1 image."
        )

    # Give each worker process a distinct but seed-derived RNG state so
    # forked workers don't replay identical Albumentations augmentations,
    # while the run as a whole stays reproducible across `num_workers` values.
    loader_generator = torch.Generator()
    loader_generator.manual_seed(cfg.training.seed)

    def _worker_init_fn(worker_id: int):
        worker_seed = cfg.training.seed + worker_id
        np.random.seed(worker_seed)
        random.seed(worker_seed)

    train_loader = DataLoader(
        train_dataset,
        batch_size=cfg.data.batch_size,
        shuffle=True,
        num_workers=cfg.data.num_workers,
        worker_init_fn=_worker_init_fn if cfg.data.num_workers > 0 else None,
        generator=loader_generator,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=cfg.data.batch_size,
        shuffle=False,
        num_workers=cfg.data.num_workers,
    )

    # Model configuration
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        try:
            # Test actual kernel execution to detect SM/kernel incompatibility
            test_tensor = torch.randn(1, 3, 32, 32).to(device)
            test_layer = torch.nn.Conv2d(3, 3, 3).to(device)
            test_layer(test_tensor)
        except Exception as e:
            logger.warning(
                f"Warning: CUDA is available but incompatible with PyTorch binary: {e}"
            )
            logger.warning("Falling back to CPU mode.")
            device = torch.device("cpu")

    logger.info(f"Using device: {device}")

    if cfg.model.name == "ensemble":
        freeze = cfg.model.get("freeze_backbones", False)
        model = ARGUSEnsemble(pretrained=cfg.model.pretrained, freeze_backbones=freeze)
    else:
        model = ARGUSBackbone(
            model_name=cfg.model.name,
            pretrained=cfg.model.pretrained,
            drop_rate=cfg.model.drop_rate,
        )
    model.to(device)

    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=cfg.training.lr, weight_decay=cfg.training.weight_decay
    )

    # Initialize AMP GradScaler if enabled
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

    # Run latency profiling benchmark
    p95_latency = profile_p95_latency(model, device, image_size)
    logger.info(f"p95 Inference Latency: {p95_latency:.2f} ms")

    # Start MLflow run
    with mlflow.start_run(run_name=f"{cfg.model.name}_run") as active_run:
        # Save run ID to local file for CI/CD gates
        run_id = active_run.info.run_id
        with open("latest_run_id.txt", "w") as f:
            f.write(run_id)

        # Log parameters
        mlflow.log_param("model_name", cfg.model.name)
        mlflow.log_param("lr", cfg.training.lr)
        mlflow.log_param("epochs", cfg.training.epochs)
        mlflow.log_param("batch_size", cfg.data.batch_size)
        mlflow.log_param("image_size", image_size)
        mlflow.log_param("use_amp", use_amp)
        # Logged so downstream reporting (e.g. the model card) can state the
        # actual training-set size instead of assuming it matches whatever
        # sample size a prior run used.
        mlflow.log_param("train_size", len(train_dataset))
        mlflow.log_param("val_size", len(val_dataset))
        mlflow.log_metric("p95_latency_ms", p95_latency)

        best_val_apcer = 1.0
        checkpoint_path = None

        for epoch in range(cfg.training.epochs):
            model.train()
            train_loss = 0.0

            for imgs, labels in train_loader:
                imgs, labels = imgs.to(device), labels.to(device)

                optimizer.zero_grad()

                # Autocast forward pass under AMP
                with torch.cuda.amp.autocast(enabled=use_amp):
                    outputs = model(imgs)
                    loss = criterion(outputs["logit"], labels)

                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()

                train_loss += loss.item() * imgs.size(0)

            train_loss /= len(train_loader.dataset)

            # Validation loop
            model.eval()
            val_loss = 0.0
            all_labels = []
            all_probs = []

            with torch.no_grad():
                for imgs, labels in val_loader:
                    imgs, labels = imgs.to(device), labels.to(device)
                    with torch.cuda.amp.autocast(enabled=use_amp):
                        outputs = model(imgs)
                        loss = criterion(outputs["logit"], labels)

                    val_loss += loss.item() * imgs.size(0)

                    probs = torch.sigmoid(outputs["logit"])
                    all_labels.extend(labels.cpu().numpy())
                    all_probs.extend(probs.cpu().numpy())

            val_loss /= len(val_loader.dataset)
            all_labels = np.array(all_labels)
            all_probs = np.array(all_probs)

            # Compute challenge-specific metrics
            apcer, bpcer, opt_threshold = compute_apcer_at_target_bpcer(
                all_labels, all_probs, target_bpcer=0.01
            )
            audet = compute_audet(all_labels, all_probs)

            logger.info(
                f"Epoch {epoch + 1}/{cfg.training.epochs} - Train Loss: {train_loss:.4f} - Val Loss: {val_loss:.4f} - APCER@1%BPCER: {apcer:.4f} - AuDET: {audet:.4f}"
            )

            # Log metrics to MLflow
            mlflow.log_metric("train_loss", train_loss, step=epoch)
            mlflow.log_metric("val_loss", val_loss, step=epoch)
            mlflow.log_metric("val_apcer_at_1percent_bpcer", apcer, step=epoch)
            mlflow.log_metric("val_audet", audet, step=epoch)

            # Log learnable weights if ensemble is used
            if cfg.model.name == "ensemble":
                weights_val = torch.softmax(model.weights, dim=0).detach().cpu().numpy()
                logger.info(
                    f"Ensemble Aggregation Weights: EffNet={weights_val[0]:.4f}, "
                    f"ConvNeXt={weights_val[1]:.4f}, EVA={weights_val[2]:.4f}"
                )
                mlflow.log_metric("weight_effnet", float(weights_val[0]), step=epoch)
                mlflow.log_metric("weight_convnext", float(weights_val[1]), step=epoch)
                mlflow.log_metric("weight_eva", float(weights_val[2]), step=epoch)

            # Save champion checkpoint
            if apcer < best_val_apcer:
                best_val_apcer = apcer
                checkpoint_path = f"best_{cfg.model.name}.pth"
                torch.save(model.state_dict(), checkpoint_path)
                mlflow.log_artifact(checkpoint_path)
                logger.info(f"Saved best model checkpoint with APCER: {apcer:.4f}")

        # Register model to the Model Registry
        if checkpoint_path and os.path.exists(checkpoint_path):
            logger.info(
                f"Registering model version '{cfg.mlflow.registered_model_name}' to MLflow Model Registry..."
            )
            model.load_state_dict(
                torch.load(checkpoint_path, map_location=device, weights_only=True)
            )
            mlflow.pytorch.log_model(
                pytorch_model=model,
                artifact_path="model",
                registered_model_name=cfg.mlflow.registered_model_name,
            )


if __name__ == "__main__":
    main()
