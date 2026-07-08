#!/usr/bin/env bash
# ==============================================================================
# ARGUS Daily Drift Detection Automation Script
# Calculates PSI over the last 24 hours of classification logs.
# ==============================================================================

set -euo pipefail

# Project root directory detection
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Configurable environment variables with safe defaults
LOG_PATH="${AUDIT_LOG_FILE:-${PROJECT_ROOT}/logs/audit.log}"
BASELINE_PATH="${DRIFT_BASELINE_PATH:-${PROJECT_ROOT}/configs/drift_baseline.json}"
THRESHOLD="${DRIFT_THRESHOLD:-0.2}"
WINDOW_HOURS="${DRIFT_WINDOW_HOURS:-24.0}"
REPORT_PATH="${DRIFT_REPORT_PATH:-${PROJECT_ROOT}/outputs/drift_report.json}"

echo "======================================================================"
echo "ARGUS Model Drift Monitor: Running scheduled evaluation"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "Log File:  ${LOG_PATH}"
echo "Baseline:  ${BASELINE_PATH}"
echo "Threshold: ${THRESHOLD}"
echo "Window:    ${WINDOW_HOURS} hours"
echo "Report:    ${REPORT_PATH}"
echo "======================================================================"

if [ ! -f "${LOG_PATH}" ]; then
    echo "ERROR: Audit log file not found at ${LOG_PATH}."
    echo "Please ensure the API is running with AUDIT_LOG_FILE configured."
    exit 1
fi

if [ ! -f "${BASELINE_PATH}" ]; then
    echo "ERROR: Baseline scores file not found at ${BASELINE_PATH}."
    exit 1
fi

# Run the drift detection Python script
# Using the current PYTHONPATH to resolve src/ packages
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"

set +e
python3 "${PROJECT_ROOT}/src/mlops/drift_detection.py" \
    --baseline-path "${BASELINE_PATH}" \
    --log-path "${LOG_PATH}" \
    --threshold "${THRESHOLD}" \
    --window-hours "${WINDOW_HOURS}" \
    --output-report "${REPORT_PATH}"
DRIFT_EXIT_CODE=$?
set -e

echo "======================================================================"
if [ ${DRIFT_EXIT_CODE} -eq 0 ]; then
    echo "SUCCESS: Drift check completed. Model distribution is stable."
    exit 0
elif [ ${DRIFT_EXIT_CODE} -eq 2 ]; then
    echo "WARNING: Drift detected! PSI exceeds the warning threshold of ${THRESHOLD}."
    echo "Downstream alerting triggered. Refer to drift report for details: ${REPORT_PATH}"
    exit 2
else
    echo "ERROR: Drift detection job failed with exit code ${DRIFT_EXIT_CODE}."
    exit 1
fi
