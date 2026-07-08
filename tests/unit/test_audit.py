import io
import json
import logging
from PIL import Image
from fastapi.testclient import TestClient
from src.api.main import app
from src.api.audit import audit_logger, AuditJSONFormatter

client = TestClient(app)


# A custom handler to capture logs in memory for testing assertions
class MemoryHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        # Format the record to get the JSON string output
        self.records.append(self.format(record))


def test_audit_log_captured_for_inference():
    """
    Assert that a successful classification request generates a structured audit log
    containing the required fields, and ensures no PII or raw image binary data is logged.
    """
    # 1. Attach memory handler to the audit logger
    mem_handler = MemoryHandler()
    mem_handler.setFormatter(AuditJSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S%z"))
    audit_logger.addHandler(mem_handler)

    try:
        # 2. Trigger a successful classification
        img = Image.new("RGB", (100, 100), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        response = client.post(
            "/classify",
            files={"file": ("test.jpg", buf, "image/jpeg")},
            headers={"X-Request-ID": "audit-test-123"},
        )
        assert response.status_code == 200

        # 3. Assert a log record was created
        assert len(mem_handler.records) == 1
        log_json = json.loads(mem_handler.records[0])

        # 4. Assert required audit fields are present at top level (flat JSON)
        assert log_json["request_id"] == "audit-test-123"
        assert log_json["method"] == "POST"
        assert log_json["endpoint"] == "/classify"
        assert log_json["status_code"] == 200
        assert "latency_ms" in log_json
        assert log_json["model_version"] == "v1.3.0"
        assert log_json["result"] in ("genuine", "fraud")
        assert "fraud_score" in log_json
        assert "confidence" in log_json
        assert "requires_human_review" in log_json

        # 5. Assert NO sensitive info, PII or image binary is logged
        for val in log_json.values():
            val_str = str(val)
            # Ensure no base64 attention map or raw file bytes are present
            assert len(val_str) < 500
            assert "image" not in val_str.lower()
            assert "base64" not in val_str.lower()

    finally:
        # Cleanup handler
        audit_logger.removeHandler(mem_handler)


def test_audit_log_captured_for_failures():
    """
    Assert that invalid/bad requests still generate a structured audit log containing
    request metadata and status codes.
    """
    mem_handler = MemoryHandler()
    mem_handler.setFormatter(AuditJSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S%z"))
    audit_logger.addHandler(mem_handler)

    try:
        # Send invalid text file
        buf = io.BytesIO(b"not an image file")
        response = client.post(
            "/classify",
            files={"file": ("test.txt", buf, "text/plain")},
            headers={"X-Request-ID": "audit-fail-123"},
        )
        assert response.status_code == 422

        # Assert log was generated
        assert len(mem_handler.records) == 1
        log_json = json.loads(mem_handler.records[0])

        assert log_json["request_id"] == "audit-fail-123"
        assert log_json["method"] == "POST"
        assert log_json["endpoint"] == "/classify"
        assert log_json["status_code"] == 422
        assert "latency_ms" in log_json

        # Model did not run, so model-specific metrics should not be present
        assert "model_version" not in log_json
        assert "result" not in log_json

    finally:
        audit_logger.removeHandler(mem_handler)


def test_audit_log_not_captured_for_metrics_and_health():
    """
    Assert that calls to /health or /metrics do not log to the audit logger.
    """
    mem_handler = MemoryHandler()
    mem_handler.setFormatter(AuditJSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S%z"))
    audit_logger.addHandler(mem_handler)

    try:
        response_health = client.get("/health")
        assert response_health.status_code == 200

        response_metrics = client.get("/metrics")
        assert response_metrics.status_code == 200

        # Neither should generate audit log entries
        assert len(mem_handler.records) == 0

    finally:
        audit_logger.removeHandler(mem_handler)
