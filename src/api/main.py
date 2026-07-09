import io
import os
import time
import uuid
import base64
import logging
import json
import asyncio
import threading
from contextlib import asynccontextmanager
import numpy as np
import torch
import albumentations as A
from albumentations.pytorch import ToTensorV2
from PIL import Image
from fastapi import FastAPI, Request, File, UploadFile, Header, HTTPException, Response
from pydantic import BaseModel
from cryptography.fernet import Fernet
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from src.api.monitoring import (
    PrometheusMonitoringMiddleware,
    argus_api_fraud_score_distribution,
)
from src.api.audit import AuditLoggingMiddleware
from src.models.baseline import ARGUSBackbone
from src.models.ensemble import ARGUSEnsemble
from src.api.retraining import router as retraining_router

# Setup logging compliant with EU AI Act (no PII, no image binaries)
logger = logging.getLogger("ARGUS_API")
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}',
)

# 1. Ephemeral Secure Storage Configuration
HUMAN_REVIEW_ENCRYPTION_KEY = os.getenv("HUMAN_REVIEW_ENCRYPTION_KEY", None)
if not HUMAN_REVIEW_ENCRYPTION_KEY:
    HUMAN_REVIEW_ENCRYPTION_KEY = Fernet.generate_key().decode()
    logger.warning(
        '"HUMAN_REVIEW_ENCRYPTION_KEY is not set. Generated a dynamic key for runtime secure storage."'
    )
fernet = Fernet(HUMAN_REVIEW_ENCRYPTION_KEY.encode())

HUMAN_REVIEW_DIR = os.getenv("HUMAN_REVIEW_DIR", "/tmp/human_review")
os.makedirs(HUMAN_REVIEW_DIR, exist_ok=True)

# Human-review routing policy: low-confidence or boundary-ambiguous
# predictions get a human second look. Config-driven rather than hardcoded
# so the policy can be tuned per deployment without a code change.
HUMAN_REVIEW_CONFIDENCE_THRESHOLD = float(
    os.getenv("HUMAN_REVIEW_CONFIDENCE_THRESHOLD", "0.70")
)
HUMAN_REVIEW_SCORE_BAND_LOW = float(os.getenv("HUMAN_REVIEW_SCORE_BAND_LOW", "0.40"))
HUMAN_REVIEW_SCORE_BAND_HIGH = float(os.getenv("HUMAN_REVIEW_SCORE_BAND_HIGH", "0.60"))


# 2. Strict 24-Hour TTL Background Task
async def clean_expired_human_review_payloads():
    while True:
        try:
            now = time.time()
            count = 0
            for f in os.listdir(HUMAN_REVIEW_DIR):
                if f.endswith(".enc"):
                    fp = os.path.join(HUMAN_REVIEW_DIR, f)
                    # 24 hours = 86400 seconds
                    if now - os.path.getmtime(fp) > 86400:
                        os.remove(fp)
                        count += 1
            if count > 0:
                logger.info(
                    f'"Cleaned up {count} expired human review payloads (strict 24h TTL)"'
                )
        except Exception as e:
            logger.error(f'"Error in human review TTL cleanup daemon: {e}"')
        # Check every hour
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the background cleanup task
    cleanup_task = asyncio.create_task(clean_expired_human_review_payloads())
    yield
    # Shutdown: Clean up task execution context
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="ARGUS Identity Verification API", version="1.3.0", lifespan=lifespan
)
app.add_middleware(AuditLoggingMiddleware)
app.add_middleware(PrometheusMonitoringMiddleware)
app.include_router(retraining_router)


@app.get("/metrics")
def metrics():
    """
    Exposes Prometheus format API telemetry metrics.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Load model configuration from environment or fallback defaults.
# EfficientNet-B4 matches the champion checkpoint baked into the Docker
# image (checkpoints/champion_efficientnet_b4.pth) — see prepare_submission.py.
_DEFAULT_CHECKPOINT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "checkpoints",
    "champion_efficientnet_b4.pth",
)
MODEL_NAME = os.getenv("MODEL_NAME", "efficientnet_b4")
CHECKPOINT_PATH = os.getenv("MODEL_CHECKPOINT_PATH", _DEFAULT_CHECKPOINT_PATH)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if DEVICE.type == "cuda":
    try:
        # Active compatibility check
        test_tensor = torch.randn(1, 3, 32, 32).to(DEVICE)
        test_layer = torch.nn.Conv2d(3, 3, 3).to(DEVICE)
        _ = test_layer(test_tensor)
        logger.info('"CUDA compatibility verification passed."')
    except Exception as e:
        logger.warning(
            f'"CUDA compatibility verification failed ({e}). Falling back to CPU."'
        )
        DEVICE = torch.device("cpu")

logger.info(f'"Initializing model: {MODEL_NAME} on device: {DEVICE}"')

# Load the model architecture
if MODEL_NAME == "ensemble":
    model = ARGUSEnsemble(pretrained=False, freeze_backbones=True)
else:
    model = ARGUSBackbone(model_name=MODEL_NAME, pretrained=False)

if CHECKPOINT_PATH and os.path.exists(CHECKPOINT_PATH):
    logger.info(f'"Loading checkpoint: {CHECKPOINT_PATH}"')
    model.load_state_dict(
        torch.load(CHECKPOINT_PATH, map_location=DEVICE, weights_only=True)
    )
else:
    logger.warning('"No model checkpoint loaded. Running with initialized weights."')

model.to(DEVICE)
model.eval()

# /classify serves requests from FastAPI's threadpool, and saliency-map
# generation below mutates shared state on this single model instance
# (zero_grad + backward populate .grad tensors on its parameters/input).
# Concurrent requests without this lock would race on that shared state and
# could return corrupted saliency maps. Inference is fast enough that
# serializing this section is not a meaningful throughput bottleneck.
_inference_lock = threading.Lock()

# Select appropriate resolution based on model architecture
IMAGE_SIZE = (
    448
    if "eva" in MODEL_NAME or MODEL_NAME == "ensemble"
    else (384 if "convnext" in MODEL_NAME else 380)
)

# Input image transformation pipeline
transform = A.Compose(
    [
        A.Resize(IMAGE_SIZE, IMAGE_SIZE),
        A.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ToTensorV2(),
    ]
)


class ClassificationResponse(BaseModel):
    request_id: str
    result: str
    fraud_score: float
    confidence: float
    requires_human_review: bool
    attention_map_base64: str
    model_version: str
    latency_ms: float


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "model": MODEL_NAME,
        "device": str(DEVICE),
        "version": "1.3.0",
    }


@app.post("/classify", response_model=ClassificationResponse)
def classify_image(
    request: Request,
    file: UploadFile = File(...),
    x_request_id: str = Header(None, alias="X-Request-ID"),
):
    start_time = time.perf_counter()
    req_id = x_request_id or str(uuid.uuid4())

    # Read binary content synchronously to utilize threadpool concurrency
    content = file.file.read()
    content_len = len(content)

    # 1. Size Validation (< 15MB)
    if content_len > 15 * 1024 * 1024:
        logger.error(
            f'"Size validation failed for request_id: {req_id}. Size: {content_len} bytes"'
        )
        raise HTTPException(status_code=413, detail="IMAGE_TOO_LARGE")

    # 2. Format & Corruption Validation (JPEG/PNG only)
    if not (
        content.startswith(b"\xff\xd8") or content.startswith(b"\x89PNG\r\n\x1a\n")
    ):
        logger.error(
            f'"Format validation failed for request_id: {req_id}. Unknown magic bytes."'
        )
        raise HTTPException(status_code=422, detail="INVALID_IMAGE_FORMAT")

    try:
        img_io = io.BytesIO(content)
        pil_img = Image.open(img_io)
        if pil_img.format not in ("JPEG", "PNG"):
            logger.error(
                f'"Format validation failed for request_id: {req_id}. Format: {pil_img.format}"'
            )
            raise HTTPException(status_code=422, detail="INVALID_IMAGE_FORMAT")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f'"Image corruption validation failed for request_id: {req_id}. Error: {e}"'
        )
        raise HTTPException(status_code=422, detail="CORRUPT_IMAGE")

    # Convert to RGB to handle palette / alpha transparency channels
    pil_img = pil_img.convert("RGB")
    img_arr = np.array(pil_img)

    # Apply Albumentations normalization
    augmented = transform(image=img_arr)
    input_tensor = augmented["image"].unsqueeze(0).to(DEVICE)

    # Enable gradients to generate visual attention/saliency maps
    input_tensor.requires_grad = True

    # Inference execution block
    try:
        with _inference_lock:
            # Zero model gradients to prevent leakage and optimize memory cleanup
            model.zero_grad(set_to_none=True)

            # Forward pass
            outputs = model(input_tensor)
            logit = outputs["logit"]

            # Backward pass on logit to compute gradients w.r.t input pixels
            logit.backward()

            # Compute absolute maximum saliency across the RGB channels
            saliency, _ = torch.max(input_tensor.grad.data.abs(), dim=1)
            saliency = saliency.squeeze(0).cpu().numpy()

        # Normalize saliency map to 0-255 uint8 format
        sal_min, sal_max = saliency.min(), saliency.max()
        if sal_max > sal_min:
            saliency = (saliency - sal_min) / (sal_max - sal_min)
        saliency = (saliency * 255.0).astype(np.uint8)

        # Base64 encode the attention map PNG
        sal_pil = Image.fromarray(saliency)
        buf = io.BytesIO()
        sal_pil.save(buf, format="PNG")
        attention_map_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        # Compute scores and decision
        fraud_score = float(torch.sigmoid(logit).item())
        result = "fraud" if fraud_score >= 0.5 else "genuine"

        # Record fraud score in Prometheus telemetry histogram
        argus_api_fraud_score_distribution.labels(result=result).observe(fraud_score)

        # Confidence score scaling (0.0 to 1.0)
        confidence = float(abs(fraud_score - 0.5) * 2.0)

        # Trigger human review for low-confidence or boundary-ambiguous scores
        requires_human_review = (
            confidence < HUMAN_REVIEW_CONFIDENCE_THRESHOLD
            or HUMAN_REVIEW_SCORE_BAND_LOW <= fraud_score <= HUMAN_REVIEW_SCORE_BAND_HIGH
        )

        # Route payload to temporary secure storage if human review is required
        if requires_human_review:
            try:
                review_payload = {
                    "request_id": req_id,
                    "fraud_score": fraud_score,
                    "confidence": confidence,
                    "image_base64": base64.b64encode(content).decode("utf-8"),
                    "attention_map_base64": attention_map_base64,
                    "timestamp": time.time(),
                }
                payload_bytes = json.dumps(review_payload).encode("utf-8")
                encrypted_payload = fernet.encrypt(payload_bytes)

                out_path = os.path.join(HUMAN_REVIEW_DIR, f"{req_id}.enc")
                with open(out_path, "wb") as f_out:
                    f_out.write(encrypted_payload)
            except Exception as store_err:
                logger.error(
                    f'"Failed to route to human review queue for request_id: {req_id}. Error: {store_err}"'
                )

    except Exception as e:
        logger.error(
            f'"Inference execution failed for request_id: {req_id}. Error: {e}"'
        )
        raise HTTPException(status_code=500, detail="INFERENCE_FAILED")

    latency_ms = float((time.perf_counter() - start_time) * 1000.0)

    # Store metadata in request state for the AuditLoggingMiddleware
    log_payload = {
        "request_id": req_id,
        "model_version": "v1.3.0",
        "result": result,
        "fraud_score": round(fraud_score, 4),
        "confidence": round(confidence, 4),
        "requires_human_review": requires_human_review,
        "latency_ms": round(latency_ms, 2),
    }
    request.state.audit_log = log_payload

    return ClassificationResponse(
        request_id=req_id,
        result=result,
        fraud_score=fraud_score,
        confidence=confidence,
        requires_human_review=requires_human_review,
        attention_map_base64=attention_map_base64,
        model_version="v1.3.0",
        latency_ms=latency_ms,
    )
