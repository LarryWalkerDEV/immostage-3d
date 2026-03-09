# =============================================================================
# ImmoStage 3D — RunPod Worker Image (Slim)
#
# Phase 1: No nerfstudio/COLMAP — tests basic pipeline
# Phase 2: Add nerfstudio + COLMAP for full 3DGS
#
# Build: docker build -t larrywalker/immostage-3d-worker:latest .
# Push:  docker push larrywalker/immostage-3d-worker:latest
# =============================================================================

FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1

# System deps for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Application dependencies (no torch, no nerfstudio)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Application code
WORKDIR /app
COPY *.py .

CMD ["python", "-u", "handler.py"]
