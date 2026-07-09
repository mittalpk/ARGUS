import json
import zipfile
from unittest.mock import patch
import mlflow
from scripts.package_compliance_evidence import (
    find_dvc_files,
    generate_model_card,
    generate_conformity_assessment,
    run_security_scan,
    package_evidence,
)


def test_find_dvc_files(tmp_path):
    """
    Assert that DVC files are discovered and parsed successfully.
    """
    # Create mock dvc file
    dvc_dir = tmp_path / "data"
    dvc_dir.mkdir()
    dvc_file = dvc_dir / "splits.dvc"
    dvc_file.write_text("outs:\n- md5: mockhash123\n  path: splits\n")

    # Call function
    results = find_dvc_files(str(tmp_path))
    assert "data/splits.dvc" in results
    assert "mockhash123" in str(results["data/splits.dvc"])


def test_generate_model_card_without_training_run(tmp_path):
    """
    With no MLflow run to report on, the card must say so plainly rather
    than asserting a performance figure that was never measured.
    """
    empty_tracking_uri = f"sqlite:///{tmp_path}/empty_mlflow.db"

    card = generate_model_card(
        str(tmp_path),
        tracking_uri=empty_tracking_uri,
        experiment_name="Nonexistent_Experiment",
    )
    assert "ARGUS Model Card" in card
    assert "v1.3.0" in card
    assert "No completed training run found" in card


def test_generate_model_card_with_training_run(tmp_path):
    """
    When a real MLflow run has logged the challenge metrics, the card must
    report the actual measured values, not a hardcoded claim.
    """
    tracking_uri = f"sqlite:///{tmp_path}/mlflow.db"
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("Test_Champion_Training")

    with mlflow.start_run(run_name="efficientnet_b4_run") as run:
        mlflow.log_param("model_name", "efficientnet_b4")
        mlflow.log_param("epochs", 3)
        mlflow.log_param("batch_size", 8)
        mlflow.log_param("image_size", 380)
        mlflow.log_param("train_size", 700)
        mlflow.log_param("val_size", 150)
        mlflow.log_metric("val_apcer_at_1percent_bpcer", 0.1234)
        mlflow.log_metric("val_audet", 0.5678)
        mlflow.log_metric("p95_latency_ms", 42.5)
        run_id = run.info.run_id

    card = generate_model_card(
        str(tmp_path),
        tracking_uri=tracking_uri,
        experiment_name="Test_Champion_Training",
    )
    assert run_id in card
    assert "efficientnet_b4" in card
    assert "0.1234" in card
    assert "0.5678" in card
    assert "42.5" in card
    assert "700" in card and "150" in card
    # These metrics aren't suspiciously perfect, so no overfitting caveat
    assert "Caveat" not in card


def test_generate_model_card_flags_suspiciously_perfect_metrics(tmp_path):
    """
    Near-zero APCER/AuDET must not be presented as a clean win without a
    caveat — that pattern is exactly what let the original audit's fabricated
    "Achieved" claims through unquestioned.
    """
    tracking_uri = f"sqlite:///{tmp_path}/mlflow.db"
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("Test_Perfect_Training")

    with mlflow.start_run(run_name="efficientnet_b4_run"):
        mlflow.log_param("model_name", "efficientnet_b4")
        mlflow.log_param("train_size", 48546)
        mlflow.log_param("val_size", 10403)
        mlflow.log_metric("val_apcer_at_1percent_bpcer", 0.0)
        mlflow.log_metric("val_audet", 0.0)

    card = generate_model_card(
        str(tmp_path),
        tracking_uri=tracking_uri,
        experiment_name="Test_Perfect_Training",
    )
    assert "Caveat" in card
    assert "suspicion" in card


def test_generate_conformity_assessment():
    """
    Assert conformity mapping highlights key high-risk AI system Articles.
    """
    assessment = generate_conformity_assessment()
    assert "Article 9" in assessment
    assert "Article 12" in assessment
    assert "Article 14" in assessment


@patch("subprocess.run")
def test_run_security_scan_not_installed(mock_run, tmp_path):
    """
    Assert fallback JSON placeholder is written if scanner is missing.
    """
    # Trigger FileNotFoundError to simulate tool missing on system
    mock_run.side_effect = FileNotFoundError()

    output_file = tmp_path / "bandit_report.json"
    status = run_security_scan(["bandit", "args"], str(output_file), "Bandit SAST")

    assert status["status"] == "NOT_INSTALLED"
    assert output_file.exists()

    with open(output_file, "r") as f:
        data = json.load(f)
    assert data["status"] == "NOT_INSTALLED"
    assert data["scanner"] == "Bandit SAST"


def test_package_evidence_flow(tmp_path):
    """
    Assert the end-to-end evidence packaging stages all assets and produces a valid ZIP file.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Setup DVC splits file
    data_dir = repo_root / "data"
    data_dir.mkdir()
    dvc_file = data_dir / "splits.dvc"
    dvc_file.write_text("md5: 8ca8efcba0\n")

    # Setup mock drift report & retraining state
    outputs_dir = repo_root / "outputs"
    outputs_dir.mkdir()
    drift_report = outputs_dir / "drift_report.json"
    drift_report.write_text(json.dumps({"psi": 0.05, "drift_detected": False}))

    retrain_state = data_dir / "retraining_state.json"
    retrain_state.write_text(json.dumps([]))

    zip_output = outputs_dir / "compliance_evidence_pack.zip"

    # Execute packager
    package_evidence(
        repo_root=str(repo_root),
        output_zip_path=str(zip_output),
        drift_report_path=str(drift_report),
        retraining_state_path=str(retrain_state),
    )

    assert zip_output.exists()

    # Validate ZIP contents
    with zipfile.ZipFile(zip_output, "r") as z:
        names = z.namelist()
        assert "dvc_hashes.json" in names
        assert "change_log.txt" in names
        assert "model_card.md" in names
        assert "conformity_assessment.md" in names
        assert "data_processing_records.json" in names
        assert "drift_report.json" in names
        assert "retraining_state.json" in names
        assert "sast_bandit_report.json" in names
        assert "secret_scan_report.json" in names
        assert "dependency_scan_report.json" in names
