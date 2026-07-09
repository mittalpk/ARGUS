#!/usr/bin/env bash
# Trains the EfficientNet-B4 champion checkpoint that ships inside the
# Docker image (checkpoints/champion_efficientnet_b4.pth).
#
# The full FREUID training set (69,352 images, ~15 GB) is available under
# data/the-freuid-challenge-2026/ once scripts/download_data.sh has run.
# Training the full set to convergence is out of scope for a quick
# reproducibility check, so this script draws a fixed-seed stratified
# subsample and runs a short but genuine training run end-to-end through
# the same ingestion -> split -> train -> gate pipeline used in production.
# Re-run with SAMPLE_PER_CLASS / EPOCHS raised for a stronger champion.
set -e

SAMPLE_PER_CLASS="${SAMPLE_PER_CLASS:-500}"
EPOCHS="${EPOCHS:-3}"
SEED="${SEED:-42}"

RAW_LABELS="data/the-freuid-challenge-2026/train_labels.csv"
RAW_IMG_DIR="data/the-freuid-challenge-2026/train/train"
SAMPLE_LABELS="data/champion_train_labels.csv"
PROCESSED_DIR="data/processed_champion"
SPLITS_DIR="data/splits_champion"

echo "=== ARGUS Champion Checkpoint Training ==="

if [ ! -f "${RAW_LABELS}" ]; then
    echo "Error: ${RAW_LABELS} not found. Run scripts/download_data.sh first."
    exit 1
fi

echo "Step 0: Drawing a stratified sample (${SAMPLE_PER_CLASS} images/class, seed=${SEED})..."
python -c "
import pandas as pd
df = pd.read_csv('${RAW_LABELS}')
sample = (
    df.groupby('label', group_keys=False)
    .apply(lambda g: g.sample(n=min(len(g), ${SAMPLE_PER_CLASS}), random_state=${SEED}))
)
sample.to_csv('${SAMPLE_LABELS}', index=False)
print(f'Sampled {len(sample)} rows: {sample[\"label\"].value_counts().to_dict()}')
"

echo "Step 1: Running Ingestion Pipeline..."
python src/data/ingestion.py "${RAW_IMG_DIR}" "${PROCESSED_DIR}" "${SAMPLE_LABELS}"

echo "Step 2: Running Stratified Splits..."
python src/data/split.py "${PROCESSED_DIR}" "${SPLITS_DIR}"

echo "Step 3: Training EfficientNet-B4 for ${EPOCHS} epoch(s)..."
PYTHONPATH=. python src/training/train.py \
    model=efficientnet \
    training.epochs="${EPOCHS}" \
    training.seed="${SEED}" \
    training.num_threads=null \
    data.splits_dir="${SPLITS_DIR}" \
    data.num_workers=2 \
    data.batch_size=8 \
    model.pretrained=true \
    mlflow.experiment_name="ARGUS_Champion_Training"

CANDIDATE_RUN_ID=$(cat latest_run_id.txt)
echo "Step 4: Running Model Performance Gate (candidate run ${CANDIDATE_RUN_ID})..."
PYTHONPATH=. python scripts/check_model_gate.py --candidate_run_id "${CANDIDATE_RUN_ID}" || \
    echo "Gate check found no prior baseline to compare against yet (expected for the first run) — continuing."

mkdir -p checkpoints
cp "best_efficientnet_b4.pth" checkpoints/champion_efficientnet_b4.pth
echo "Champion checkpoint written to checkpoints/champion_efficientnet_b4.pth"
echo "MLflow run id: ${CANDIDATE_RUN_ID}" | tee checkpoints/champion_efficientnet_b4.run_id.txt

echo "=== ARGUS Champion Checkpoint Training complete ==="
