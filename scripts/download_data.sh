#!/usr/bin/env bash

# ARGUS Dataset Acquisition Script
# Downloads and extracts the FREUID IJCAI-ECAI 2026 Challenge dataset.

set -e

echo "=== ARGUS Dataset Acquisition started ==="

# Load credentials from .env if present
if [ -f .env ]; then
    echo "Loading credentials from .env..."
    export $(grep -v '^#' .env | xargs)
fi

# Map KAGGLE_API_TOKEN to KAGGLE_KEY if provided
if [ -n "${KAGGLE_API_TOKEN}" ] && [ -z "${KAGGLE_KEY}" ]; then
    export KAGGLE_KEY="${KAGGLE_API_TOKEN}"
fi

# 1. Verify Kaggle Credentials (either via env vars or kaggle.json)
if [ -z "${KAGGLE_USERNAME}" ] || [ -z "${KAGGLE_KEY}" ]; then
    if [ ! -f "${HOME}/.kaggle/kaggle.json" ]; then
        echo "Error: Kaggle API credentials not found."
        echo "Please configure KAGGLE_USERNAME and KAGGLE_KEY (or KAGGLE_API_TOKEN) in your .env file or place kaggle.json at ~/.kaggle/."
        exit 1
    fi
    # Ensure correct permissions on kaggle credentials if using file fallback
    chmod 600 "${HOME}/.kaggle/kaggle.json"
fi

# 2. Verify local disk has at least 60 GB free space
AVAILABLE_SPACE_GB=$(df -BG . | tail -n 1 | awk '{print $4}' | tr -d 'G')
if [ "${AVAILABLE_SPACE_GB}" -lt 60 ]; then
    echo "Error: Insufficient disk space. Required: 60 GB, Available: ${AVAILABLE_SPACE_GB} GB."
    exit 1
fi

# 3. Create Target Directories
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
