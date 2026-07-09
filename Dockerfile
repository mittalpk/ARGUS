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

# NOTE: no pretrained-ImageNet-weight pre-download here. Inference always
# constructs the model with pretrained=False (see prepare_submission.py) and
# loads the fine-tuned competition checkpoint below instead, so caching the
# generic ImageNet weights at build time would only bloat the image.

# ==========================================
# Stage 2: Runner
# ==========================================
FROM python:3.10-slim AS runner

# Create a system user/group for the app's own files. The default runtime
# user is root (see the USER directive removed below) rather than this user,
# because /submissions is a host-supplied bind mount whose ownership this
# image does not control: the reproducibility contract's own documented
# validation command (`docker run ... -v "$(pwd)/out:/submissions" ...`)
# creates that directory with standard host permissions (owner-writable
# only), and a fixed non-root UID inside the container has no way to write
# to it — verified directly: this exact failure reproduces with the
# checklist's own example command. Root bypasses that permission mismatch,
# which matters more here than the non-root hardening does, since
# `--network none` means there's no listening service in this batch-inference
# mode for non-root isolation to protect in the first place. The FastAPI
# server mode (`docker run ... uvicorn ...`) is network-facing and should
# still be run behind non-root isolation at the orchestration layer
# (e.g. a Kubernetes non-root securityContext) if deployed that way.
RUN groupadd -g 10001 argus && \
    useradd -u 10001 -g argus -m -s /sbin/nologin argus

# Install system dependencies required for OpenCV, Pillow, and system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage with correct ownership
COPY --from=builder --chown=argus:argus /root/.local /home/argus/.local

# Copy application code with correct ownership
WORKDIR /app
COPY --chown=argus:argus src/ /app/src/
COPY --chown=argus:argus prepare_submission.py /app/
COPY --chown=argus:argus entrypoint.sh /app/

# Bake in the trained champion checkpoint so the sandbox never needs to
# download weights at inference time (network is disabled at inference).
COPY --chown=argus:argus checkpoints/ /app/checkpoints/

# Set HOME so Python's user-site package resolution finds the packages
# installed under /home/argus/.local above even though the runtime user is
# root (root's default HOME is /root, which would otherwise miss them).
ENV HOME=/home/argus
ENV PATH=/home/argus/.local/bin:$PATH

# Expose FastAPI API port
EXPOSE 8000

# Docker Healthcheck utilizing python's built-in urllib
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start using entrypoint wrapper
ENTRYPOINT ["/app/entrypoint.sh"]
CMD []
