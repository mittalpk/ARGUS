import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.api.main import app
from src.api.retraining import save_state

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state_file(tmp_path):
    """
    Isolate state file during tests.
    """
    temp_state = tmp_path / "retraining_state.json"
    with patch("src.api.retraining.STATE_FILE", str(temp_state)):
        # Clear file if exists
        if temp_state.exists():
            temp_state.unlink()
        yield


def test_request_retraining_drift():
    """
    Assert that drift submission successfully creates a pending retraining request.
    """
    response = client.post("/retrain", json={"psi": 0.25, "drift_detected": True})
    assert response.status_code == 201
    data = response.json()
    assert "request_id" in data
    assert data["status"] == "PENDING_APPROVAL"
    assert data["psi"] == 0.25
    assert data["drift_detected"] is True
    assert data["dispatched"] is False


def test_request_retraining_no_drift():
    """
    Assert that submission without drift is rejected with 400 Bad Request.
    """
    response = client.post("/retrain", json={"psi": 0.05, "drift_detected": False})
    assert response.status_code == 400
    assert "drift is detected" in response.json()["detail"]


def test_duplicate_prevention():
    """
    Assert that duplicate request fails if a pending one is already open.
    """
    # Create first request
    res1 = client.post("/retrain", json={"psi": 0.25, "drift_detected": True})
    assert res1.status_code == 201

    # Attempt second request
    res2 = client.post("/retrain", json={"psi": 0.30, "drift_detected": True})
    assert res2.status_code == 400
    assert "already pending approval" in res2.json()["detail"]


def test_rate_limiting():
    """
    Assert rate limiting: cannot request or approve retraining if one was executed in the last 7 days.
    """
    # 1. Set up state with an approved request resolved 2 days ago
    resolved_time = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    past_approved_request = {
        "request_id": "resolved-run-123",
        "status": "APPROVED",
        "psi": 0.35,
        "drift_detected": True,
        "submitted_at": resolved_time,
        "resolved_at": resolved_time,
        "approved_by": "Lead Data Scientist",
        "dispatched": True,
    }
    save_state([past_approved_request])

    # 2. Try to request retraining -> should fail with 429 Too Many Requests
    response = client.post("/retrain", json={"psi": 0.25, "drift_detected": True})
    assert response.status_code == 429
    assert "rate limit exceeded" in response.json()["detail"]


def test_approve_retraining_rbac(monkeypatch):
    """
    Assert role-based access control on retraining approval requires both the
    correct role header AND the shared-secret API key (the role header alone
    is caller-supplied and cannot authorize anything by itself).
    """
    monkeypatch.setattr(
        "src.api.retraining.RETRAINING_APPROVAL_API_KEY", "test-secret-key"
    )

    # 1. Submit request
    res = client.post("/retrain", json={"psi": 0.25, "drift_detected": True})
    assert res.status_code == 201
    req_id = res.json()["request_id"]

    # 2. Try to approve with incorrect role -> should fail with 403
    headers_se = {"X-User-Role": "Software Engineer", "X-API-Key": "test-secret-key"}
    res_se = client.post(f"/retrain/{req_id}/approve", headers=headers_se)
    assert res_se.status_code == 403

    # 3. Correct role but missing/incorrect API key -> should still fail with 403
    headers_no_key = {"X-User-Role": "Lead Data Scientist"}
    res_no_key = client.post(f"/retrain/{req_id}/approve", headers=headers_no_key)
    assert res_no_key.status_code == 403

    headers_wrong_key = {
        "X-User-Role": "Lead Data Scientist",
        "X-API-Key": "not-the-secret",
    }
    res_wrong_key = client.post(f"/retrain/{req_id}/approve", headers=headers_wrong_key)
    assert res_wrong_key.status_code == 403

    # 4. Correct role AND correct API key -> should succeed
    headers_ds = {"X-User-Role": "Lead Data Scientist", "X-API-Key": "test-secret-key"}
    res_ds = client.post(f"/retrain/{req_id}/approve", headers=headers_ds)
    assert res_ds.status_code == 200
    data = res_ds.json()
    assert data["status"] == "APPROVED"
    assert data["approved_by"] == "Lead Data Scientist"
    assert data["dispatched"] is True
    assert data["resolved_at"] is not None


def test_approve_retraining_fails_closed_when_unconfigured(monkeypatch):
    """
    If no approval secret is configured server-side, approval must be refused
    outright rather than silently trusting the caller-supplied role header.
    """
    monkeypatch.setattr("src.api.retraining.RETRAINING_APPROVAL_API_KEY", None)

    res = client.post("/retrain", json={"psi": 0.25, "drift_detected": True})
    assert res.status_code == 201
    req_id = res.json()["request_id"]

    headers_ds = {"X-User-Role": "Lead Data Scientist", "X-API-Key": "anything"}
    res_ds = client.post(f"/retrain/{req_id}/approve", headers=headers_ds)
    assert res_ds.status_code == 503


def test_list_requests():
    """
    Assert requests query filtering works.
    """
    # Setup some mock entries
    mock_data = [
        {
            "request_id": "r1",
            "status": "PENDING_APPROVAL",
            "psi": 0.25,
            "drift_detected": True,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "resolved_at": None,
            "approved_by": None,
            "dispatched": False,
        },
        {
            "request_id": "r2",
            "status": "APPROVED",
            "psi": 0.35,
            "drift_detected": True,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "approved_by": "Lead Data Scientist",
            "dispatched": True,
        },
    ]
    save_state(mock_data)

    # List all
    res_all = client.get("/retrain/requests")
    assert res_all.status_code == 200
    assert len(res_all.json()) == 2

    # Filter status
    res_pending = client.get("/retrain/requests?status=pending_approval")
    assert res_pending.status_code == 200
    assert len(res_pending.json()) == 1
    assert res_pending.json()[0]["request_id"] == "r1"


@patch("urllib.request.urlopen")
def test_automated_trigger_on_drift(mock_urlopen):
    """
    Verify integration between the drift detection CLI and the retraining API.
    """
    mock_response = MagicMock()
    mock_response.getcode.return_value = 201
    mock_urlopen.return_value.__enter__.return_value = mock_response

    # Import drift detection script main runner block or call CLI logic directly
    from src.mlops.drift_detection import trigger_retraining_api

    # Simulate triggering API through trigger_retraining_api function
    trigger_retraining_api(url="http://test-server/retrain", psi=0.25)

    # Verify HTTP POST was requested via urllib
    assert mock_urlopen.call_count == 1
    args, kwargs = mock_urlopen.call_args
    req = args[0]
    assert req.full_url == "http://test-server/retrain"
    assert req.method == "POST"
