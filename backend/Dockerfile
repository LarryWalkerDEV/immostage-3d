# =============================================================================
# ImmoStage 3D — RunPod Worker Image
#
# Base: RunPod PyTorch (CUDA 12.1, Python 3.10)
# Adds: COLMAP (photogrammetry), nerfstudio (NeRF + Gaussian splatting)
# App:  handler.py (RunPod serverless entrypoint)
#
# Build: docker build -t larrywalker/immostage-3d-worker:latest .
# Push:  docker push larrywalker/immostage-3d-worker:latest
# =============================================================================

FROM runpod/pytorch:1.0.3-cu1290-torch260-ubuntu2204

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    NS_DISABLE_TELEMETRY=1 \
    # Cache nerfstudio models in /workspace so they survive pod restarts
    NS_MODEL_CACHE_DIR=/workspace/model_cache

# ---------------------------------------------------------------------------
# System dependencies
# COLMAP: structure-from-motion used by nerfstudio's data pipeline
# ffmpeg: video decoding for future video-room support
# libgl / libglib: required by OpenCV (used in nerfstudio internals)
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    colmap \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Python: nerfstudio
# Pinned to >=1.1.0 for Gaussian splatting (3DGS) support.
# PyTorch wheel index must match the CUDA version in the base image.
# ---------------------------------------------------------------------------
RUN pip install --no-cache-dir \
    "nerfstudio>=1.1.0" \
    --extra-index-url https://download.pytorch.org/whl/cu129

# ---------------------------------------------------------------------------
# Application dependencies
# requirements.txt contains supabase, httpx, pillow, etc.
# ---------------------------------------------------------------------------
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# ---------------------------------------------------------------------------
# Application code
# Copy all Python files from backend/ into /app
# ---------------------------------------------------------------------------
WORKDIR /app
COPY *.py .

# ---------------------------------------------------------------------------
# Entrypoint
# RunPod calls handler.py which implements the serverless handler interface:
#   def handler(job) -> dict
# The -u flag disables output buffering so logs appear in real time.
# ---------------------------------------------------------------------------
CMD ["python", "-u", "handler.py"]
