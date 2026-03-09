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

# Install runpod WITHOUT its heavy deps (fastapi[all] conflicts with supabase httpx pin)
# We only use runpod.serverless.start(), not the built-in web server
RUN pip install --no-cache-dir --no-deps runpod==1.6.2

# Application dependencies (no torch, no nerfstudio)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Application code
WORKDIR /app
COPY *.py .

CMD ["python", "-u", "handler.py"]
