#!/bin/bash
set -e

echo "=== ARGUS E2E Pipeline Verification ==="

# Clean old test run files
rm -rf data/processed_e2e data/splits_e2e latest_run_id.txt

# 1. Run Ingestion (US-01)
echo "Step 1: Running Ingestion Pipeline..."
python src/data/ingestion.py \
    data/the-freuid-challenge-2026/train_sample/train_sample \
    data/processed_e2e \
    data/the-freuid-challenge-2026/train_sample_labels.csv

# 2. Run Splitting (US-01)
echo "Step 2: Running Stratified Splits..."
python src/data/split.py \
    data/processed_e2e \
    data/splits_e2e

# 3. Run Training (US-02 / US-03)
echo "Step 3: Running Model Training (1 epoch)..."
PYTHONPATH=. python src/training/train.py \
    model=convnext \
    training.epochs=1 \
    data.splits_dir=data/splits_e2e \
    data.num_workers=0 \
    data.batch_size=2 \
    model.pretrained=False \
    mlflow.experiment_name="ARGUS_E2E_Validation"

# 4. Run Model Performance Gate Check (US-04)
echo "Step 4: Executing Model Performance Gate..."
if [ -f latest_run_id.txt ]; then
    CANDIDATE_RUN_ID=$(cat latest_run_id.txt)
    echo "Latest Run ID: $CANDIDATE_RUN_ID"
    PYTHONPATH=. python scripts/check_model_gate.py --candidate_run_id $CANDIDATE_RUN_ID --threshold 2.0
else
    echo "Error: latest_run_id.txt was not generated!"
    exit 1
fi

# Clean up generated test outputs
rm -rf data/processed_e2e data/splits_e2e latest_run_id.txt

echo "=== ARGUS E2E Pipeline PASSED successfully ==="
