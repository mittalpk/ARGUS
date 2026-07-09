import os
import logging
import secrets
import argparse
import mlflow
from mlflow.tracking import MlflowClient

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ARGUS_Promotion")

ALLOWED_PROMOTION_ROLES = {"Lead Data Scientist", "Project Lead"}

# The --role flag is just an operator-supplied string — it can't authorize
# anything on its own. Promotion additionally requires a shared-secret API
# key so only operators holding that secret can promote a model version.
PROMOTION_API_KEY = os.getenv("ARGUS_PROMOTION_API_KEY")


class AccessDeniedError(PermissionError):
    """Raised when a user with an unauthorized role tries to transition model stages."""

    pass


def promote_model(
    model_name: str,
    version: int,
    stage: str,
    user_role: str,
    tracking_uri: str = None,
    api_key: str = None,
):
    """
    Transition a model version in the MLflow Model Registry to a new lifecycle stage.
    Enforces Role-Based Access Control (RBAC).

    Args:
        model_name: Name of the registered model.
        version: Version number of the model.
        stage: Target stage (e.g., 'Staging', 'Production', 'Archived').
        user_role: The role of the user requesting the promotion.
        tracking_uri: Optional tracking URI path. Fallback to env or config default.
        api_key: Shared secret proving the caller is authorized to act as
            `user_role`. Required whenever ARGUS_PROMOTION_API_KEY is set.
    """
    logger.info(
        f"Promotion requested for model '{model_name}' v{version} to stage '{stage}' by user with role '{user_role}'"
    )

    # 1. Enforce Role-Based Access Control (RBAC): role plus a shared secret.
    if user_role not in ALLOWED_PROMOTION_ROLES:
        error_msg = f"User role '{user_role}' is unauthorized to promote models to '{stage}'. Only {ALLOWED_PROMOTION_ROLES} are allowed."
        logger.error(error_msg)
        raise AccessDeniedError(error_msg)

    if PROMOTION_API_KEY and not (
        api_key and secrets.compare_digest(api_key, PROMOTION_API_KEY)
    ):
        error_msg = "Invalid or missing promotion API key."
        logger.error(error_msg)
        raise AccessDeniedError(error_msg)

    # 2. Configure MLflow connection
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    else:
        # Check standard config fallback or env variables
        tracking_uri = mlflow.get_tracking_uri()

    logger.info(f"Connecting to MLflow Tracking Server at: {tracking_uri}")
    client = MlflowClient()

    # 3. Transition model version stage
    try:
        # Transition stage
        updated_details = client.transition_model_version_stage(
            name=model_name,
            version=str(version),
            stage=stage,
            archive_existing_versions=True,
        )
        logger.info(
            f"Successfully transitioned model '{model_name}' v{version} to stage '{stage}'"
        )
        return updated_details
    except Exception as e:
        logger.error(f"Failed to transition model stage in MLflow Registry. Error: {e}")
        raise e


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ARGUS MLOps Model Promotion Governance Utility"
    )
    parser.add_argument(
        "--model-name", type=str, required=True, help="Name of the registered model"
    )
    parser.add_argument(
        "--version", type=int, required=True, help="Model version number"
    )
    parser.add_argument(
        "--stage",
        type=str,
        required=True,
        choices=["Staging", "Production", "Archived", "None"],
        help="Target stage",
    )
    parser.add_argument(
        "--role", type=str, required=True, help="Role of the executing operator"
    )
    parser.add_argument(
        "--tracking-uri",
        type=str,
        default="sqlite:///mlflow.db",
        help="MLflow tracking URI",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Shared secret authorizing this promotion; required if "
        "ARGUS_PROMOTION_API_KEY is set in the environment",
    )

    args = parser.parse_args()

    try:
        promote_model(
            model_name=args.model_name,
            version=args.version,
            stage=args.stage,
            user_role=args.role,
            tracking_uri=args.tracking_uri,
            api_key=args.api_key,
        )
    except AccessDeniedError:
        exit(3)
    except Exception:
        exit(1)
