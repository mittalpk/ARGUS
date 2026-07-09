import os
import sys
import json
import logging
import argparse
from datetime import datetime, timedelta, timezone
import numpy as np

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ARGUS_Drift_Detection")


def parse_timestamp(ts_str: str) -> datetime:
    """
    Parse ISO-8601 timestamp strings robustly, handling different timezone formats.
    """
    # Standardize 'Z' to UTC offset
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"

    # Try to parse with standard isoformat
    try:
        dt = datetime.fromisoformat(ts_str)
    except ValueError:
        # Handle cases with no colon in timezone offset, e.g. +0200
        if len(ts_str) > 6 and (ts_str[-5] == "+" or ts_str[-5] == "-"):
            ts_str = ts_str[:-2] + ":" + ts_str[-2:]
        dt = datetime.fromisoformat(ts_str)

    # Ensure datetime object is timezone-aware; fallback to UTC if naive
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_baseline_scores(baseline_path: str) -> list:
    """
    Load baseline scores from a JSON file.
    """
    if not os.path.exists(baseline_path):
        raise FileNotFoundError(f"Baseline file not found at: {baseline_path}")

    with open(baseline_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Baseline scores file must contain a JSON list of floats.")

    scores = [float(x) for x in data]
    if len(scores) == 0:
        raise ValueError("Baseline dataset is empty.")
    return scores


def load_target_scores_from_logs(log_path: str, window_hours: float = 24.0) -> list:
    """
    Read target scores from audit log file (JSON-lines), filtering by window_hours.
    If window_hours is <= 0, all classification scores in the log file are used.
    """
    if not os.path.exists(log_path):
        raise FileNotFoundError(f"Audit log file not found at: {log_path}")

    scores = []
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=window_hours) if window_hours > 0 else None

    with open(log_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse line {line_num} in log file: {e}")
                continue

            # Filter only classification endpoints that succeeded
            if (
                record.get("endpoint") != "/classify"
                or record.get("status_code") != 200
            ):
                continue

            # If a window is configured, verify timestamp eligibility
            if cutoff_time:
                ts_str = record.get("timestamp")
                if not ts_str:
                    logger.warning(
                        f"Line {line_num} does not contain a timestamp field."
                    )
                    continue
                try:
                    record_time = parse_timestamp(ts_str)
                    if record_time < cutoff_time:
                        continue
                except Exception as e:
                    logger.warning(
                        f"Skipping line {line_num} due to timestamp parsing error: {e}"
                    )
                    continue

            # Extract score
            score = record.get("fraud_score")
            if score is not None:
                try:
                    scores.append(float(score))
                except (ValueError, TypeError):
                    logger.warning(
                        f"Invalid fraud_score value at line {line_num}: {score}"
                    )

    return scores


def calculate_psi(
    baseline_scores: list, target_scores: list, num_bins: int = 10
) -> float:
    """
    Calculate the Population Stability Index (PSI) between two sets of scores.
    Uses equal-width binning in [0.0, 1.0].
    """
    if not baseline_scores:
        raise ValueError("Baseline scores list is empty. Cannot calculate PSI.")
    if not target_scores:
        raise ValueError("Target scores list is empty. Cannot calculate PSI.")

    # Bin scores into [0, 0.1, 0.2, ..., 1.0]
    bins = np.linspace(0.0, 1.0, num_bins + 1)

    baseline_counts, _ = np.histogram(baseline_scores, bins=bins)
    target_counts, _ = np.histogram(target_scores, bins=bins)

    # Convert counts to probability distributions
    baseline_probs = baseline_counts / len(baseline_scores)
    target_probs = target_counts / len(target_scores)

    # Avoid division by zero and log(0) with Laplace-style offset
    epsilon = 1e-4
    baseline_probs = np.where(baseline_probs == 0, epsilon, baseline_probs)
    target_probs = np.where(target_probs == 0, epsilon, target_probs)

    # Re-normalize to sum to 1.0
    baseline_probs = baseline_probs / np.sum(baseline_probs)
    target_probs = target_probs / np.sum(target_probs)

    # Calculate PSI
    psi_value = np.sum(
        (target_probs - baseline_probs) * np.log(target_probs / baseline_probs)
    )
    return float(psi_value)


def run_drift_check(
    baseline_path: str,
    log_path: str,
    threshold: float = 0.2,
    window_hours: float = 24.0,
    output_report_path: str = None,
) -> tuple:
    """
    Execute the full drift detection pipeline.
    """
    logger.info(
        f"Starting drift check using baseline: {baseline_path} and logs: {log_path}"
    )

    baseline_scores = load_baseline_scores(baseline_path)
    target_scores = load_target_scores_from_logs(log_path, window_hours=window_hours)

    logger.info(f"Loaded {len(baseline_scores)} baseline scores.")
    logger.info(
        f"Loaded {len(target_scores)} target scores from logs (window_hours={window_hours})."
    )

    if len(target_scores) == 0:
        logger.warning(
            "No target scores collected within the specified monitoring window. Skipping drift calculation."
        )
        # If no target data, we cannot calculate PSI
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "SKIPPED",
            "message": "No target scores collected in monitoring window.",
            "target_samples": 0,
        }
        if output_report_path:
            os.makedirs(
                os.path.dirname(os.path.abspath(output_report_path)), exist_ok=True
            )
            with open(output_report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
        # Exiting with 0 when there's no data to analyze, but logging a warning
        return 0.0, False

    psi_val = calculate_psi(baseline_scores, target_scores)
    drift_detected = psi_val > threshold

    logger.info(f"Calculated Population Stability Index (PSI): {psi_val:.4f}")

    if drift_detected:
        logger.error(
            f"CRITICAL DRIFT ALERT: Model prediction drift detected! "
            f"PSI value ({psi_val:.4f}) exceeds threshold ({threshold})."
        )
    else:
        logger.info(
            f"PSI is within acceptable bounds ({psi_val:.4f} <= {threshold}). No drift detected."
        )

    # Write summary report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "SUCCESS",
        "psi": round(psi_val, 6),
        "drift_detected": drift_detected,
        "threshold": threshold,
        "baseline_samples": len(baseline_scores),
        "target_samples": len(target_scores),
        "window_hours": window_hours,
    }

    if output_report_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_report_path)), exist_ok=True)
        with open(output_report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Drift report written to: {output_report_path}")

    return psi_val, drift_detected


def trigger_retraining_api(url: str, psi: float):
    """
    HTTP POST call to the retraining endpoint when drift is detected.
    """
    logger.info(f"Triggering automated retraining API at {url}...")
    try:
        import urllib.request
        import urllib.error
        import urllib.parse

        # --trigger-retrain-url is operator-configured, not end-user input,
        # but urlopen will happily follow file:// and other non-HTTP schemes
        # if given one — restrict to http(s) so a misconfigured URL can't
        # turn this into a local file read.
        scheme = urllib.parse.urlsplit(url).scheme
        if scheme not in ("http", "https"):
            logger.error(
                f"Refusing to trigger retraining at non-HTTP(S) URL scheme: {scheme!r}"
            )
            return

        headers = {"Content-Type": "application/json"}
        payload_data = json.dumps({"psi": psi, "drift_detected": True}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload_data, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:  # nosec B310 - scheme checked above
            status_code = response.getcode()
            logger.info(
                f"Successfully posted retraining trigger to {url}. HTTP Status: {status_code}"
            )
    except Exception as e:
        logger.error(f"Failed to trigger automated retraining API: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ARGUS MLOps Automated Drift Detection Tool"
    )
    parser.add_argument(
        "--baseline-path",
        type=str,
        default="configs/drift_baseline.json",
        help="Path to the JSON file containing baseline scores",
    )
    parser.add_argument(
        "--log-path",
        type=str,
        required=True,
        help="Path to the audit log file containing prediction records",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.2,
        help="PSI threshold above which drift is flagged (default: 0.2)",
    )
    parser.add_argument(
        "--window-hours",
        type=float,
        default=24.0,
        help="Hour window to filter audit logs (default: 24.0, set to 0 to analyze all logs)",
    )
    parser.add_argument(
        "--output-report",
        type=str,
        default=None,
        help="Optional path to write a JSON summary report file",
    )
    parser.add_argument(
        "--trigger-retrain-url",
        type=str,
        default=None,
        help="API URL to trigger retraining if drift is detected",
    )

    args = parser.parse_args()

    try:
        psi, is_drift = run_drift_check(
            baseline_path=args.baseline_path,
            log_path=args.log_path,
            threshold=args.threshold,
            window_hours=args.window_hours,
            output_report_path=args.output_report,
        )
        # Automatically trigger retraining if drift detected and URL is configured
        if is_drift and args.trigger_retrain_url:
            trigger_retraining_api(args.trigger_retrain_url, psi)

        # Exit code 2 if drift detected, else 0
        if is_drift:
            sys.exit(2)
        sys.exit(0)
    except Exception as exc:
        logger.exception(f"Drift detection execution failed: {exc}")
        sys.exit(1)
