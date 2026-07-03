#!/usr/bin/env python3

# ARGUS Dataset Acquisition Script via kagglehub
# Downloads and extracts the FREUID IJCAI-ECAI 2026 Challenge dataset.

import os
import shutil
from dotenv import load_dotenv

# Load env variables from .env
load_dotenv()

# Map KAGGLE_API_TOKEN to KAGGLE_KEY if provided
if "KAGGLE_API_TOKEN" in os.environ and "KAGGLE_KEY" not in os.environ:
    os.environ["KAGGLE_KEY"] = os.environ["KAGGLE_API_TOKEN"]

# Verify credentials exist
if not os.environ.get("KAGGLE_USERNAME") or not os.environ.get("KAGGLE_KEY"):
    print("Error: Kaggle API credentials not found in environment or .env file.")
    print("Please set KAGGLE_USERNAME and KAGGLE_KEY / KAGGLE_API_TOKEN.")
    exit(1)

import kagglehub

print("Downloading dataset using kagglehub...")
COMPETITION_NAME = "the-freuid-challenge-2026-ijcai-ecai"

try:
    path = kagglehub.competition_download(COMPETITION_NAME)
    print("Path to competition files in cache:", path)

    target_dir = "data/the-freuid-challenge-2026"
    os.makedirs("data", exist_ok=True)
    
    if os.path.exists(target_dir):
        print(f"Removing old target directory {target_dir}...")
        shutil.rmtree(target_dir)

    print(f"Copying dataset files to {target_dir}...")
    shutil.copytree(path, target_dir)
    print("=== ARGUS Dataset Acquisition successfully completed! ===")

except Exception as e:
    print(f"Failed to download dataset: {e}")
    exit(1)
