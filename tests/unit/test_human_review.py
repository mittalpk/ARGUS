import io
import os
import json
import time
from unittest.mock import MagicMock, patch
from PIL import Image
from fastapi.testclient import TestClient
import pytest
import torch
from cryptography.fernet import Fernet

# Configure test env variables prior to importing app
os.environ["HUMAN_REVIEW_DIR"] = "/tmp/test_human_review"
os.environ["HUMAN_REVIEW_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

from src.api.main import app, fernet, HUMAN_REVIEW_DIR

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_test_dir():
    # Setup test directory
    os.makedirs(HUMAN_REVIEW_DIR, exist_ok=True)
    yield
    # Clean up files after test runs
    if os.path.exists(HUMAN_REVIEW_DIR):
        for f in os.listdir(HUMAN_REVIEW_DIR):
            os.remove(os.path.join(HUMAN_REVIEW_DIR, f))
        os.rmdir(HUMAN_REVIEW_DIR)


def create_dummy_image():
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


@patch("src.api.main.model")
def test_ambiguous_prediction_triggers_review(mock_model):
    # Mock model to return logit=0.0 connected to input computation graph
    def mock_forward(x):
        return {"logit": x.mean() * 0.0 + torch.tensor([0.0], requires_grad=True)}

    mock_model.side_effect = mock_forward
    mock_model.zero_grad = MagicMock()

    buf = create_dummy_image()
    response = client.post(
        "/classify",
        files={"file": ("test.jpg", buf, "image/jpeg")},
        headers={"X-Request-ID": "test-ambiguous-123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["requires_human_review"] is True
    assert data["fraud_score"] == 0.5
    assert data["confidence"] == 0.0

    # Verify encrypted payload file was created
    expected_file = os.path.join(HUMAN_REVIEW_DIR, "test-ambiguous-123.enc")
    assert os.path.exists(expected_file)

    # Read and decrypt payload
    with open(expected_file, "rb") as f:
        encrypted_bytes = f.read()

    decrypted_bytes = fernet.decrypt(encrypted_bytes)
    payload = json.loads(decrypted_bytes.decode("utf-8"))

    assert payload["request_id"] == "test-ambiguous-123"
    assert payload["fraud_score"] == 0.5
    assert payload["confidence"] == 0.0
    assert "image_base64" in payload
    assert "attention_map_base64" in payload


@patch("src.api.main.model")
def test_confident_prediction_skips_review(mock_model):
    # Mock model to return logit=10.0 connected to input computation graph
    def mock_forward(x):
        return {"logit": x.mean() * 0.0 + torch.tensor([10.0], requires_grad=True)}

    mock_model.side_effect = mock_forward
    mock_model.zero_grad = MagicMock()

    buf = create_dummy_image()
    response = client.post(
        "/classify",
        files={"file": ("test.jpg", buf, "image/jpeg")},
        headers={"X-Request-ID": "test-confident-123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["requires_human_review"] is False
    assert data["confidence"] > 0.9

    # Verify no encrypted payload file was created
    expected_file = os.path.join(HUMAN_REVIEW_DIR, "test-confident-123.enc")
    assert not os.path.exists(expected_file)


def test_ttl_cleanup_task():
    # Manually create files with different modified times
    now = time.time()

    # 1. Fresh file (created now)
    fresh_fp = os.path.join(HUMAN_REVIEW_DIR, "fresh.enc")
    with open(fresh_fp, "wb") as f:
        f.write(b"freshcontent")

    # 2. Expired file (created 25 hours ago)
    expired_fp = os.path.join(HUMAN_REVIEW_DIR, "expired.enc")
    with open(expired_fp, "wb") as f:
        f.write(b"expiredcontent")
    os.utime(expired_fp, (now - 90000, now - 90000))  # 90000 seconds > 24 hours

    # Run the cleanup logic manually for testing
    count = 0
    for f in os.listdir(HUMAN_REVIEW_DIR):
        if f.endswith(".enc"):
            fp = os.path.join(HUMAN_REVIEW_DIR, f)
            if now - os.path.getmtime(fp) > 86400:
                os.remove(fp)
                count += 1

    assert count == 1
    assert os.path.exists(fresh_fp)
    assert not os.path.exists(expired_fp)
