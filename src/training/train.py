import os
import random
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
from src.models.baseline import ARGUSBackbone
from src.training.metrics import compute_apcer_at_target_bpcer, compute_audet

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
        img_name = row['image_id']
        img_path = os.path.join(self.img_dir, img_name)
        
        # Load image safely
        img = np.array(Image.open(img_path).convert('RGB'))
        label = float(row['label'])
        
        if self.transform:
            augmented = self.transform(image=img)
            img = augmented['image']
            
        return img, torch.tensor(label, dtype=torch.float32)

@hydra.main(version_base=None, config_path="../../configs", config_name="config")
def main(cfg: DictConfig):
    set_seed(cfg.training.seed)
    
    # Configure MLflow
    mlflow.set_tracking_uri(cfg.mlflow.tracking_uri)
    mlflow.set_experiment(cfg.mlflow.experiment_name)
    
    # Albumentations transforms
    train_transform = A.Compose([
        A.Resize(cfg.data.image_size, cfg.data.image_size),
        A.HorizontalFlip(p=0.5),
        A.RandomBrightnessContrast(p=0.2),
        A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ToTensorV2()
    ])
    
    val_transform = A.Compose([
        A.Resize(cfg.data.image_size, cfg.data.image_size),
        A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ToTensorV2()
    ])
    
    # Load dataset partitions
    train_csv = os.path.join(cfg.data.splits_dir, "train_labels.csv")
    val_csv = os.path.join(cfg.data.splits_dir, "val_labels.csv")
    
    train_dataset = ARGUSDataset(train_csv, os.path.join(cfg.data.splits_dir, "train"), transform=train_transform)
    val_dataset = ARGUSDataset(val_csv, os.path.join(cfg.data.splits_dir, "val"), transform=val_transform)
    
    train_loader = DataLoader(train_dataset, batch_size=cfg.data.batch_size, shuffle=True, num_workers=cfg.data.num_workers)
    val_loader = DataLoader(val_dataset, batch_size=cfg.data.batch_size, shuffle=False, num_workers=cfg.data.num_workers)
    
    # Model configuration
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        try:
            # Test actual kernel execution to detect SM/kernel incompatibility
            test_tensor = torch.randn(1, 3, 32, 32).to(device)
            test_layer = torch.nn.Conv2d(3, 3, 3).to(device)
            test_layer(test_tensor)
        except Exception as e:
            print(f"Warning: CUDA is available but incompatible with PyTorch binary: {e}")
            print("Falling back to CPU mode.")
            device = torch.device("cpu")
            
    print(f"Using device: {device}")
    
    model = ARGUSBackbone(model_name=cfg.model.name, pretrained=cfg.model.pretrained, drop_rate=cfg.model.drop_rate)
    model.to(device)
    
    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.training.lr, weight_decay=cfg.training.weight_decay)
    
    # Start MLflow run
    with mlflow.start_run():
        # Log parameters
        mlflow.log_param("model_name", cfg.model.name)
        mlflow.log_param("lr", cfg.training.lr)
        mlflow.log_param("epochs", cfg.training.epochs)
        mlflow.log_param("batch_size", cfg.data.batch_size)
        
        best_val_apcer = 1.0
        
        for epoch in range(cfg.training.epochs):
            model.train()
            train_loss = 0.0
            
            for imgs, labels in train_loader:
                imgs, labels = imgs.to(device), labels.to(device)
                
                optimizer.zero_grad()
                outputs = model(imgs)
                loss = criterion(outputs['logit'], labels)
                loss.backward()
                optimizer.step()
                
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
                    outputs = model(imgs)
                    loss = criterion(outputs['logit'], labels)
                    val_loss += loss.item() * imgs.size(0)
                    
                    probs = torch.sigmoid(outputs['logit'])
                    all_labels.extend(labels.cpu().numpy())
                    all_probs.extend(probs.cpu().numpy())
            
            val_loss /= len(val_loader.dataset)
            all_labels = np.array(all_labels)
            all_probs = np.array(all_probs)
            
            # Compute challenge-specific metrics
            apcer, bpcer, opt_threshold = compute_apcer_at_target_bpcer(all_labels, all_probs, target_bpcer=0.01)
            audet = compute_audet(all_labels, all_probs)
            
            print(f"Epoch {epoch+1}/{cfg.training.epochs} - Train Loss: {train_loss:.4f} - Val Loss: {val_loss:.4f} - APCER@1%BPCER: {apcer:.4f} - AuDET: {audet:.4f}")
            
            # Log metrics to MLflow
            mlflow.log_metric("train_loss", train_loss, step=epoch)
            mlflow.log_metric("val_loss", val_loss, step=epoch)
            mlflow.log_metric("val_apcer_at_1percent_bpcer", apcer, step=epoch)
            mlflow.log_metric("val_audet", audet, step=epoch)
            
            # Save champion checkpoint
            if apcer < best_val_apcer:
                best_val_apcer = apcer
                checkpoint_path = "best_model.pth"
                torch.save(model.state_dict(), checkpoint_path)
                mlflow.log_artifact(checkpoint_path)
                print(f"Saved best model checkpoint with APCER: {apcer:.4f}")
                
if __name__ == "__main__":
    main()
