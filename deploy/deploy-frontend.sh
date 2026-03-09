#!/bin/bash
# =============================================================================
# deploy/deploy-frontend.sh
# Deploy the ImmoStage 3D frontend to Vercel (production).
#
# Prerequisites:
#   - Vercel CLI installed: npm install -g vercel
#   - Logged in: vercel login
#   - Environment variables configured in Vercel dashboard:
#       SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, RUNPOD_ENDPOINT, RUNPOD_API_KEY
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/../frontend"

echo "--- ImmoStage 3D: Deploying frontend to Vercel ---"
echo "Frontend directory: $FRONTEND_DIR"

if [ ! -d "$FRONTEND_DIR" ]; then
  echo "ERROR: frontend/ directory not found at $FRONTEND_DIR"
  exit 1
fi

cd "$FRONTEND_DIR"

# Deploy to production
npx vercel --prod

echo "--- Frontend deployed successfully ---"
