import os
import shutil
import pytest
import mlflow
from scripts.check_model_gate import check_model_performance

@pytest.fixture(scope="module")
def mock_mlflow_env(tmp_path_factory):
    # Set up temporary MLflow tracking directory
    tracking_dir = tmp_path_factory.mktemp("mlruns_mock")
    tracking_uri = f"file://{tracking_dir.as_posix()}"
    mlflow.set_tracking_uri(tracking_uri)
    
    # Set up dummy experiment
    mlflow.set_experiment("gate_test_experiment")
    
    # 1. Register historical baseline run (best_historical = 0.05)
    with mlflow.start_run() as r_hist:
        mlflow.log_metric("val_apcer_at_1percent_bpcer", 0.05)
        hist_run_id = r_hist.info.run_id
        
    # 2. Register candidate run that PASSES (0.0505 is +1.0% relative, within +2% tolerance)
    with mlflow.start_run() as r_pass:
        mlflow.log_metric("val_apcer_at_1percent_bpcer", 0.0505)
        pass_run_id = r_pass.info.run_id
        
    # 3. Register candidate run that FAILS (0.053 is +6.0% relative, exceeds +2% tolerance)
    with mlflow.start_run() as r_fail:
        mlflow.log_metric("val_apcer_at_1percent_bpcer", 0.053)
        fail_run_id = r_fail.info.run_id
        
    yield {
        "tracking_uri": tracking_uri,
        "pass_run_id": pass_run_id,
        "fail_run_id": fail_run_id,
        "hist_run_id": hist_run_id
    }

def test_model_gate_pass(mock_mlflow_env):
    env = mock_mlflow_env
    # Check PASS candidate (should return True)
    assert check_model_performance(
        candidate_run_id=env["pass_run_id"],
        tracking_uri=env["tracking_uri"],
        threshold_pct=2.0
    ) is True

def test_model_gate_fail(mock_mlflow_env):
    env = mock_mlflow_env
    # Check FAIL candidate (should return False)
    assert check_model_performance(
        candidate_run_id=env["fail_run_id"],
        tracking_uri=env["tracking_uri"],
        threshold_pct=2.0
    ) is False
