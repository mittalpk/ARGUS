import argparse
import sys
import logging
import mlflow

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_model_performance(
    candidate_run_id: str, tracking_uri: str = "mlruns", threshold_pct: float = 2.0
) -> bool:
    """
    Validates candidate run APCER against the best historical run.
    Returns True if performance gate passes, False if there is a degradation.
    """
    mlflow.set_tracking_uri(tracking_uri)
    client = mlflow.tracking.MlflowClient()

    # Retrieve the candidate run performance
    try:
        candidate_run = client.get_run(candidate_run_id)
        candidate_apcer = candidate_run.data.metrics.get("val_apcer_at_1percent_bpcer")
        if candidate_apcer is None:
            logger.error(
                f"Candidate run {candidate_run_id} has no metric 'val_apcer_at_1percent_bpcer'."
            )
            return False
        logger.info(f"Candidate model validation APCER: {candidate_apcer:.4f}")
    except Exception as e:
        logger.error(f"Failed to fetch candidate run {candidate_run_id}: {e}")
        return False

    # Get all runs in the experiment to find the previous best/champion run
    experiment_id = candidate_run.info.experiment_id
    try:
        runs = client.search_runs(
            experiment_ids=[experiment_id],
            order_by=["metrics.val_apcer_at_1percent_bpcer ASC"],
        )
        # Exclude the current candidate run itself from comparison
        historical_runs = [
            r
            for r in runs
            if r.info.run_id != candidate_run_id
            and "val_apcer_at_1percent_bpcer" in r.data.metrics
        ]

        if not historical_runs:
            logger.info(
                "No historical baseline runs found for comparison. Promoting candidate run automatically."
            )
            return True

        best_historical_run = historical_runs[0]
        best_historical_apcer = best_historical_run.data.metrics[
            "val_apcer_at_1percent_bpcer"
        ]
        logger.info(
            f"Best historical baseline validation APCER: {best_historical_apcer:.4f} (Run ID: {best_historical_run.info.run_id})"
        )

        # Lower APCER is better. Max acceptable APCER = baseline APCER * (1 + tolerance)
        max_acceptable_apcer = best_historical_apcer * (1.0 + threshold_pct / 100.0)
        logger.info(
            f"Maximum acceptable APCER threshold (with {threshold_pct}% relative tolerance): {max_acceptable_apcer:.4f}"
        )

        if candidate_apcer > max_acceptable_apcer:
            logger.error(
                f"Model Performance Gate FAILED: Candidate APCER {candidate_apcer:.4f} "
                f"exceeds maximum acceptable threshold {max_acceptable_apcer:.4f}."
            )
            return False

        logger.info("Model Performance Gate PASSED.")
        return True
    except Exception as e:
        logger.error(f"Failed historical run performance validation: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARGUS Model CI Performance Gate")
    parser.add_argument(
        "--candidate_run_id",
        type=str,
        required=True,
        help="MLflow Run ID of the candidate model",
    )
    parser.add_argument(
        "--tracking_uri", type=str, default="mlruns", help="MLflow tracking URI"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=2.0,
        help="Acceptable relative degradation threshold in %",
    )

    args = parser.parse_args()
    success = check_model_performance(
        args.candidate_run_id, args.tracking_uri, args.threshold
    )
    if not success:
        sys.exit(1)
    sys.exit(0)
