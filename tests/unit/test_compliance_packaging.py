import json
import zipfile
from unittest.mock import patch
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


def test_generate_model_card(tmp_path):
    """
    Assert that the Model Card markdown includes expected version and sections.
    """
    latest_run = tmp_path / "latest_run_id.txt"
    latest_run.write_text("mock-run-id-456")

    card = generate_model_card(str(tmp_path))
    assert "ARGUS Model Card" in card
    assert "v1.3.0" in card
    assert "mock-run-id-456" in card
    assert "APCER" in card


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
