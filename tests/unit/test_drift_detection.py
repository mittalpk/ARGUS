import json
import pytest
from datetime import datetime, timedelta, timezone
from src.mlops.drift_detection import (
    parse_timestamp,
    calculate_psi,
    load_baseline_scores,
    load_target_scores_from_logs,
    run_drift_check,
)


def test_parse_timestamp():
    """
    Verify timezone aware parsing of various ISO-8601 string formats.
    """
    # UTC format with Z suffix
    dt1 = parse_timestamp("2026-07-09T01:19:48Z")
    assert dt1.tzinfo == timezone.utc
    assert dt1.year == 2026
    assert dt1.hour == 1

    # Format with colon timezone offset
    dt2 = parse_timestamp("2026-07-09T01:19:48+02:00")
    assert dt2.tzinfo is not None
    assert dt2.utcoffset() == timedelta(hours=2)

    # Format without colon timezone offset
    dt3 = parse_timestamp("2026-07-09T01:19:48-0500")
    assert dt3.tzinfo is not None
    assert dt3.utcoffset() == -timedelta(hours=5)


def test_calculate_psi_math():
    """
    Verify mathematically sound PSI calculation, including identical and drifted cases.
    """
    # Identical distributions should have a PSI of 0
    scores_a = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]
    psi_ident = calculate_psi(scores_a, scores_a)
    assert abs(psi_ident) < 1e-5

    # Slightly shifted distributions (staying within the same bins)
    scores_b = [0.06, 0.16, 0.26, 0.36, 0.46, 0.56, 0.66, 0.76, 0.86, 0.96]
    psi_shift = calculate_psi(scores_a, scores_b)
    assert psi_shift < 0.1  # Minimal shift

    # Completely drifted distributions
    scores_drifted = [0.95] * 10  # All concentrated in the high score bin
    psi_drift = calculate_psi(scores_a, scores_drifted)
    assert psi_drift > 0.2  # Massive drift

    # Empty inputs must raise ValueError
    with pytest.raises(ValueError, match="Baseline scores list is empty"):
        calculate_psi([], scores_a)
    with pytest.raises(ValueError, match="Target scores list is empty"):
        calculate_psi(scores_a, [])


def test_load_baseline_scores(tmp_path):
    """
    Assert correct loading and validation of baseline scores JSON.
    """
    file_path = tmp_path / "baseline.json"

    # Successful load
    valid_data = [0.1, 0.5, 0.9]
    file_path.write_text(json.dumps(valid_data))
    loaded = load_baseline_scores(str(file_path))
    assert loaded == valid_data

    # Empty array
    file_path.write_text(json.dumps([]))
    with pytest.raises(ValueError, match="Baseline dataset is empty"):
        load_baseline_scores(str(file_path))

    # Invalid JSON schema
    file_path.write_text(json.dumps({"scores": [1, 2]}))
    with pytest.raises(ValueError, match="must contain a JSON list of floats"):
        load_baseline_scores(str(file_path))


def test_load_target_scores_from_logs(tmp_path):
    """
    Assert target logs are parsed and filtered correctly based on endpoint, status, and time.
    """
    log_file = tmp_path / "audit.log"
    now = datetime.now(timezone.utc)

    recent_time = (now - timedelta(hours=2)).isoformat()
    old_time = (now - timedelta(hours=30)).isoformat()

    records = [
        # Matching record
        {
            "timestamp": recent_time,
            "endpoint": "/classify",
            "status_code": 200,
            "fraud_score": 0.15,
        },
        # Older record (beyond 24 hours)
        {
            "timestamp": old_time,
            "endpoint": "/classify",
            "status_code": 200,
            "fraud_score": 0.85,
        },
        # Wrong endpoint
        {
            "timestamp": recent_time,
            "endpoint": "/health",
            "status_code": 200,
            "fraud_score": 0.5,
        },
        # Erroneous classification call
        {
            "timestamp": recent_time,
            "endpoint": "/classify",
            "status_code": 500,
            "fraud_score": 0.9,
        },
        # Matching record 2
        {
            "timestamp": recent_time,
            "endpoint": "/classify",
            "status_code": 200,
            "fraud_score": 0.45,
        },
    ]

    with open(log_file, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    # Test filtering with 24 hours window (should include only recent matching records)
    scores = load_target_scores_from_logs(str(log_file), window_hours=24.0)
    assert len(scores) == 2
    assert scores == [0.15, 0.45]

    # Test filtering with no window (should include all matching records regardless of age)
    all_scores = load_target_scores_from_logs(str(log_file), window_hours=0)
    assert len(all_scores) == 3
    assert all_scores == [0.15, 0.85, 0.45]


def test_run_drift_check(tmp_path):
    """
    Assert drift check executes correctly, determines drift state, and generates report.
    """
    baseline_file = tmp_path / "baseline.json"
    log_file = tmp_path / "audit.log"
    report_file = tmp_path / "report.json"

    # Setup baseline and target logs
    baseline_scores = [0.1] * 20 + [0.8] * 20
    baseline_file.write_text(json.dumps(baseline_scores))

    recent_time = datetime.now(timezone.utc).isoformat()
    # High drift target logs (all 0.95)
    records = [
        {
            "timestamp": recent_time,
            "endpoint": "/classify",
            "status_code": 200,
            "fraud_score": 0.95,
        }
        for _ in range(10)
    ]

    with open(log_file, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    # Run check with low threshold (0.2) -> should detect drift
    psi, is_drift = run_drift_check(
        str(baseline_file),
        str(log_file),
        threshold=0.2,
        window_hours=24.0,
        output_report_path=str(report_file),
    )

    assert is_drift is True
    assert psi > 0.2
    assert report_file.exists()

    with open(report_file, "r") as f:
        report = json.load(f)
    assert report["drift_detected"] is True
    assert report["psi"] == round(psi, 6)
    assert report["baseline_samples"] == 40
    assert report["target_samples"] == 10

    # Run check with high threshold (20.0) -> should NOT detect drift since PSI (17.7) is below 20.0
    _, is_drift_high = run_drift_check(
        str(baseline_file),
        str(log_file),
        threshold=20.0,
        window_hours=24.0,
        output_report_path=None,
    )
    assert is_drift_high is False


def test_run_drift_check_empty_target(tmp_path):
    """
    Assert drift check handles empty target scores gracefully without throwing math errors.
    """
    baseline_file = tmp_path / "baseline.json"
    log_file = tmp_path / "audit.log"
    report_file = tmp_path / "report.json"

    baseline_file.write_text(json.dumps([0.5, 0.6]))
    log_file.write_text("")  # Empty logs

    psi, is_drift = run_drift_check(
        str(baseline_file),
        str(log_file),
        threshold=0.2,
        window_hours=24.0,
        output_report_path=str(report_file),
    )

    assert psi == 0.0
    assert is_drift is False
    assert report_file.exists()

    with open(report_file, "r") as f:
        report = json.load(f)
    assert report["status"] == "SKIPPED"
    assert report["target_samples"] == 0
