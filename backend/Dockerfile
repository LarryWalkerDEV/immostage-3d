# =============================================================================
# ImmoStage 3D — RunPod Worker Image
#
# Base: NVIDIA CUDA 12.1 + Ubuntu 22.04 (~4GB vs 13GB runpod/pytorch)
# Adds: Python 3.10, PyTorch 2.6, COLMAP, nerfstudio (3DGS)
# App:  handler.py (RunPod serverless entrypoint)
#
# Build: docker build -t larrywalker/immostage-3d-worker:latest .
# Push:  docker push larrywalker/immostage-3d-worker:latest
# =============================================================================

FROM nvidia/cuda:12.1.0-devel-ubuntu22.04

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    NS_DISABLE_TELEMETRY=1 \
    NS_MODEL_CACHE_DIR=/workspace/model_cache

# ---------------------------------------------------------------------------
# System dependencies
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3.10-dev \
    python3-pip \
    git \
    colmap \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    wget \
    && ln -sf /usr/bin/python3.10 /usr/bin/python \
    && ln -sf /usr/bin/python3.10 /usr/bin/python3 \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Python: PyTorch 2.6 + CUDA 12.1
# ---------------------------------------------------------------------------
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    torch==2.6.0 torchvision==0.21.0 \
    --index-url https://download.pytorch.org/whl/cu121

# ---------------------------------------------------------------------------
# Python: nerfstudio (3DGS support)
# ---------------------------------------------------------------------------
RUN pip install --no-cache-dir "nerfstudio>=1.1.0"

# ---------------------------------------------------------------------------
# Application dependencies
# ---------------------------------------------------------------------------
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# ---------------------------------------------------------------------------
# Application code
# ---------------------------------------------------------------------------
WORKDIR /app
COPY *.py .

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
CMD ["python", "-u", "handler.py"]
