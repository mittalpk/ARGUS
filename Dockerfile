# ==========================================
# Stage 1: Builder
# ==========================================
FROM python:3.10-slim AS builder

# Install system dependencies required for building wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy dependency definition
COPY requirements.txt .

# Upgrade pip and install requirements
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# Pre-cache pretrained model weights in argus home cache directory
ENV HF_HOME=/home/argus/.cache/huggingface
ENV TORCH_HOME=/home/argus/.cache/torch
RUN mkdir -p /home/argus/.cache/huggingface /home/argus/.cache/torch

RUN python -c "import timm; timm.create_model('efficientnet_b4', pretrained=True); timm.create_model('convnextv2_base', pretrained=True); timm.create_model('eva02_large_patch14_448', pretrained=True)"

# ==========================================
# Stage 2: Runner
# ==========================================
FROM python:3.10-slim AS runner

# Create non-root system user and group
RUN groupadd -g 10001 argus && \
    useradd -u 10001 -g argus -m -s /sbin/nologin argus

# Install system dependencies required for OpenCV, Pillow, and system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /root/.local /home/argus/.local
COPY --from=builder /home/argus/.cache /home/argus/.cache

# Copy application code
WORKDIR /app
COPY src/ /app/src/
COPY prepare_submission.py /app/

# Set env path variables for the non-root user local packages
ENV PATH=/home/argus/.local/bin:$PATH
ENV HF_HOME=/home/argus/.cache/huggingface
ENV TORCH_HOME=/home/argus/.cache/torch

# Change ownership of app and cache to non-root user
RUN chown -R argus:argus /app /home/argus

# Switch to non-root user security context
USER argus

# Expose FastAPI API port
EXPOSE 8000

# Docker Healthcheck utilizing python's built-in urllib
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start the FastAPI application using uvicorn
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
