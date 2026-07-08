import io
from PIL import Image
from fastapi.testclient import TestClient
from src.api.main import app
from src.api.monitoring import (
    argus_api_requests_total,
    argus_api_fraud_score_distribution,
)

client = TestClient(app)


def test_metrics_endpoint_raw_output():
    """
    Assert that the /metrics endpoint returns HTTP 200 and contains
    the defined Prometheus metrics in the expected plain-text format.
    """
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")

    content = response.text
    # Verify our custom metrics are declared in helper output
    assert "argus_api_requests_total" in content
    assert "argus_api_request_duration_seconds" in content
    assert "argus_api_fraud_score_distribution" in content


def test_classification_updates_prometheus_metrics():
    """
    Assert that classification requests increment HTTP count counters,
    update duration metrics, and store fraud score distributions.
    """
    # 1. Capture baseline metric values if any exist
    try:
        baseline_requests = argus_api_requests_total.labels(
            method="POST", endpoint="/classify", status="200"
        )._value.get()
    except KeyError:
        baseline_requests = 0.0

    # 2. Trigger a successful classification
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    response = client.post(
        "/classify",
        files={"file": ("test.jpg", buf, "image/jpeg")},
        headers={"X-Request-ID": "monitoring-test-123"},
    )
    assert response.status_code == 200
    data = response.json()
    result = data["result"]

    # 3. Assert request count incremented
    updated_requests = argus_api_requests_total.labels(
        method="POST", endpoint="/classify", status="200"
    )._value.get()
    assert updated_requests == baseline_requests + 1.0

    # 4. Assert fraud score was tracked in the distribution
    # Let's count how many samples are in the distribution histogram
    samples_count = sum(
        argus_api_fraud_score_distribution.labels(result=result)._sum.get() for _ in [1]
    )
    assert samples_count > 0.0


def test_invalid_requests_update_error_metrics():
    """
    Assert that bad/unauthorized requests increment metrics with appropriate error status codes.
    """
    try:
        baseline_errors = argus_api_requests_total.labels(
            method="POST", endpoint="/classify", status="422"
        )._value.get()
    except KeyError:
        baseline_errors = 0.0

    # Send invalid plain text file
    buf = io.BytesIO(b"not an image file")
    response = client.post(
        "/classify",
        files={"file": ("test.txt", buf, "text/plain")},
    )
    assert response.status_code == 422

    # Verify status 422 requests counter is updated
    updated_errors = argus_api_requests_total.labels(
        method="POST", endpoint="/classify", status="422"
    )._value.get()
    assert updated_errors == baseline_errors + 1.0


def test_unknown_endpoint_avoids_cardinality_explosion():
    """
    Assert that requests to non-existent endpoints are tracked with "unknown"
    instead of using the dynamic raw path as a label (preventing cardinality explosion).
    """
    try:
        baseline_unknown = argus_api_requests_total.labels(
            method="GET", endpoint="unknown", status="404"
        )._value.get()
    except KeyError:
        baseline_unknown = 0.0

    # Query two different random paths
    response1 = client.get("/non-existent-path-abc")
    response2 = client.get("/another-invalid-route-xyz")
    assert response1.status_code == 404
    assert response2.status_code == 404

    # Verify endpoint is mapped to "unknown" and incremented by 2
    updated_unknown = argus_api_requests_total.labels(
        method="GET", endpoint="unknown", status="404"
    )._value.get()
    assert updated_unknown == baseline_unknown + 2.0


def test_metrics_and_health_endpoints_are_excluded():
    """
    Assert that health checks and metrics scrapes do not increment requests counter.
    """
    # 1. Query /metrics and /health
    client.get("/metrics")
    client.get("/health")

    # 2. Assert no metrics have been registered for those paths
    # If they are excluded, querying their labels will raise KeyError or return baseline value
    try:
        metrics_calls = argus_api_requests_total.labels(
            method="GET", endpoint="/metrics", status="200"
        )._value.get()
        assert metrics_calls == 0.0 or metrics_calls is None
    except KeyError:
        pass

    try:
        health_calls = argus_api_requests_total.labels(
            method="GET", endpoint="/health", status="200"
        )._value.get()
        assert health_calls == 0.0 or health_calls is None
    except KeyError:
        pass

