# ruff: noqa: E402
import os

ORIG_CWD = os.getcwd()
os.chdir("/tmp")

import pytest
import mlflow
import torch.nn as nn
from mlflow.tracking import MlflowClient
from src.mlops.promote_model import promote_model, AccessDeniedError

TEST_DB_URI = "sqlite:////tmp/test_mlflow.db"
MODEL_NAME = "Test_ARGUS_Classifier"


class TinyModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(10, 2)

    def forward(self, x):
        return self.fc(x)


@pytest.fixture(scope="module", autouse=True)
def setup_test_mlflow():
    # Setup SQLite tracking URI for tests
    mlflow.set_tracking_uri(TEST_DB_URI)

    # Create test experiment with writable /tmp artifact store location
    exp_name = "Test_Registry_Experiment"
    try:
        exp_id = mlflow.create_experiment(
            exp_name, artifact_location="/tmp/test_mlruns"
        )
    except Exception:
        exp = mlflow.get_experiment_by_name(exp_name)
        exp_id = exp.experiment_id
    mlflow.set_experiment(experiment_id=exp_id)

    yield
    # Restore original working directory
    os.chdir(ORIG_CWD)
    # Clean up test DB file after runs
    db_path = "/tmp/test_mlflow.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    # Clean up MLflow local artifact store folder
    import shutil

    if os.path.exists("/tmp/test_mlruns"):
        shutil.rmtree("/tmp/test_mlruns", ignore_errors=True)


def test_model_registration_and_version_counts():
    model = TinyModel()

    # Start a run and log/register model
    with mlflow.start_run():
        # First registration
        mlflow.pytorch.log_model(
            pytorch_model=model, artifact_path="model", registered_model_name=MODEL_NAME
        )

    client = MlflowClient()
    versions = client.get_latest_versions(MODEL_NAME)
    assert len(versions) == 1
    assert int(versions[0].version) == 1

    # Register version 2
    with mlflow.start_run():
        mlflow.pytorch.log_model(
            pytorch_model=model, artifact_path="model", registered_model_name=MODEL_NAME
        )

    versions = client.get_latest_versions(MODEL_NAME)
    # Verify version count increments to 2
    latest_version = max(int(v.version) for v in versions)
    assert latest_version == 2


def test_rbac_promotion_denied_for_unauthorized_roles():
    # Attempting to promote with an unauthorized role should raise AccessDeniedError
    with pytest.raises(AccessDeniedError) as exc_info:
        promote_model(
            model_name=MODEL_NAME,
            version=1,
            stage="Staging",
            user_role="Junior Data Scientist",
            tracking_uri=TEST_DB_URI,
        )
    assert "unauthorized to promote" in str(exc_info.value)

    # Verify stage was NOT changed
    client = MlflowClient()
    version_details = client.get_model_version(MODEL_NAME, "1")
    assert version_details.current_stage in (None, "None")


def test_rbac_promotion_approved_for_lead_roles():
    # Transition to Staging by Lead Data Scientist
    updated_details = promote_model(
        model_name=MODEL_NAME,
        version=1,
        stage="Staging",
        user_role="Lead Data Scientist",
        tracking_uri=TEST_DB_URI,
    )
    assert updated_details.current_stage == "Staging"

    # Transition to Production by Project Lead
    updated_details_prod = promote_model(
        model_name=MODEL_NAME,
        version=1,
        stage="Production",
        user_role="Project Lead",
        tracking_uri=TEST_DB_URI,
    )
    assert updated_details_prod.current_stage == "Production"


def test_rbac_promotion_requires_api_key_when_configured(monkeypatch):
    """
    When ARGUS_PROMOTION_API_KEY is configured, the correct role alone is no
    longer sufficient — a matching --api-key must also be supplied.
    """
    monkeypatch.setattr(
        "src.mlops.promote_model.PROMOTION_API_KEY", "test-promotion-secret"
    )

    with pytest.raises(AccessDeniedError):
        promote_model(
            model_name=MODEL_NAME,
            version=1,
            stage="Staging",
            user_role="Lead Data Scientist",
            tracking_uri=TEST_DB_URI,
            api_key=None,
        )

    updated_details = promote_model(
        model_name=MODEL_NAME,
        version=1,
        stage="Staging",
        user_role="Lead Data Scientist",
        tracking_uri=TEST_DB_URI,
        api_key="test-promotion-secret",
    )
    assert updated_details.current_stage == "Staging"
