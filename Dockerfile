# Dockerfile for FREUID Challenge 2026 Reproducibility Package
FROM python:3.10-slim

# Install system dependencies required for OpenCV, Pillow, and system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy dependency definition
COPY requirements.txt .

# Upgrade pip and install package requirements
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Run dummy instantiation during build phase to cache model structures and weights inside the image
# This ensures zero internet access is required during runtime (offline sandbox compliance)
RUN python -c "import timm; timm.create_model('convnextv2_base', pretrained=True); timm.create_model('eva02_large_patch14_448', pretrained=True)"

# Copy model architecture wrapper and core source code
COPY src/ /app/src/
COPY prepare_submission.py /app/

# Entry point triggers submission file preparation
ENTRYPOINT ["python", "prepare_submission.py"]
