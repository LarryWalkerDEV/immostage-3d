#!/bin/bash
# =============================================================================
# deploy/deploy-backend.sh
# Build and push the RunPod worker Docker image to Docker Hub.
#
# Prerequisites:
#   - Docker Desktop running
#   - Logged in to Docker Hub: docker login
#   - RunPod account with serverless endpoint configured
#
# After pushing, go to:
#   https://runpod.io/console/serverless
#   → Select your endpoint → Edit → Set image to larrywalker/immostage-3d-worker:latest
#   → Save → Workers will pull the new image on next cold start
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/../backend"
IMAGE="larrywalker/immostage-3d-worker:latest"

echo "--- ImmoStage 3D: Building backend Docker image ---"
echo "Backend directory: $BACKEND_DIR"
echo "Target image: $IMAGE"

if [ ! -d "$BACKEND_DIR" ]; then
  echo "ERROR: backend/ directory not found at $BACKEND_DIR"
  exit 1
fi

cd "$BACKEND_DIR"

# Build with BuildKit for faster layer caching
DOCKER_BUILDKIT=1 docker build \
  --platform linux/amd64 \
  -t "$IMAGE" \
  .

echo "--- Build complete. Pushing to Docker Hub ---"
docker push "$IMAGE"

echo ""
echo "--- Backend deployed successfully ---"
echo ""
echo "Next steps:"
echo "  1. Go to https://runpod.io/console/serverless"
echo "  2. Select your endpoint (immostage-3d-worker)"
echo "  3. Edit → set image to: $IMAGE"
echo "  4. Save — workers will use the new image on next cold start"
