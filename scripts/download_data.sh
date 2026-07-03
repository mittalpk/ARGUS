#!/usr/bin/env bash

# ARGUS Dataset Acquisition Script
# Downloads and extracts the FREUID IJCAI-ECAI 2026 Challenge dataset.

set -e

echo "=== ARGUS Dataset Acquisition started ==="

# 1. Verify Kaggle Credentials
if [ ! -f "${HOME}/.kaggle/kaggle.json" ]; then
    echo "Warning: Kaggle API credentials not found at ~/.kaggle/kaggle.json."
    echo "Please download your kaggle.json from Kaggle Account settings and place it in ~/.kaggle/."
    echo "For instructions, visit: https://github.com/Kaggle/kaggle-api"
    echo "Once credentials are in place, run this script again."
    exit 1
fi

# Ensure correct permissions on kaggle credentials
chmod 600 "${HOME}/.kaggle/kaggle.json"

# 2. Create Target Directories
mkdir -p data/

# 3. Download Dataset
echo "Downloading the FREUID Challenge 2026 dataset via Kaggle API..."
# Note: The competition name used in download commands
COMPETITION_NAME="the-freuid-challenge-2026-ijcai-ecai"

if [ ! -f "data/${COMPETITION_NAME}.zip" ]; then
    kaggle competitions download -c "${COMPETITION_NAME}" -p data/
else
    echo "Dataset zip file already downloaded."
fi

# 4. Extract Dataset
TARGET_DIR="data/the-freuid-challenge-2026"
if [ ! -d "${TARGET_DIR}" ]; then
    echo "Extracting dataset to ${TARGET_DIR}..."
    unzip -q "data/${COMPETITION_NAME}.zip" -d "${TARGET_DIR}"
    echo "Dataset extraction complete."
else
    echo "Dataset already extracted at ${TARGET_DIR}."
fi

echo "=== ARGUS Dataset Acquisition successfully completed! ==="
