import io
from PIL import Image
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "model" in data
    assert "version" in data


def test_classify_endpoint_success():
    # Create a dummy image
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    response = client.post(
        "/classify",
        files={"file": ("test.jpg", buf, "image/jpeg")},
        headers={"X-Request-ID": "test-req-123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "test-req-123"
    assert data["result"] in ("genuine", "fraud")
    assert isinstance(data["fraud_score"], float)
    assert isinstance(data["confidence"], float)
    assert isinstance(data["requires_human_review"], bool)
    assert "attention_map_base64" in data
    assert data["model_version"] == "v1.3.0"
    assert isinstance(data["latency_ms"], float)


def test_classify_endpoint_invalid_format():
    # Save dummy file as GIF or text
    buf = io.BytesIO(b"dummy text content")
    response = client.post("/classify", files={"file": ("test.txt", buf, "text/plain")})

    assert response.status_code == 422
    assert response.json()["detail"] == "INVALID_IMAGE_FORMAT"


def test_classify_endpoint_corrupt_image():
    # Send empty or corrupted bytes disguised as jpeg
    buf = io.BytesIO(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00corruptedbinary"
    )
    response = client.post(
        "/classify", files={"file": ("corrupt.jpg", buf, "image/jpeg")}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "CORRUPT_IMAGE"


def test_classify_endpoint_too_large():
    # Create a payload exceeding 15MB
    large_bytes = b"0" * (16 * 1024 * 1024)
    buf = io.BytesIO(large_bytes)

    response = client.post(
        "/classify", files={"file": ("large.jpg", buf, "image/jpeg")}
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "IMAGE_TOO_LARGE"
