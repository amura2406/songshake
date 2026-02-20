#!/usr/bin/env bash
# deploy.sh — Deploy Song Shake to Cloud Run + Firebase Hosting
#
# Usage:
#   ./deploy.sh                 # Full deploy (backend + frontend)
#   ./deploy.sh --backend-only  # Backend only
#   ./deploy.sh --frontend-only # Frontend only
#
set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────────────────
REGION="asia-southeast2"
SERVICE_NAME="song-shake-api"
FIREBASE_SITE="songshake999"
CORS_ORIGIN="https://${FIREBASE_SITE}.web.app"

# ─── Parse flags ─────────────────────────────────────────────────────────────
BACKEND=true
FRONTEND=true

for arg in "$@"; do
  case $arg in
    --backend-only) FRONTEND=false ;;
    --frontend-only) BACKEND=false ;;
    --help|-h)
      echo "Usage: $0 [--backend-only | --frontend-only]"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg"
      exit 1
      ;;
  esac
done

# ─── Backend: Cloud Run ──────────────────────────────────────────────────────
if [ "$BACKEND" = true ]; then
  echo "═══════════════════════════════════════════════════"
  echo "  🚀 Deploying Backend to Cloud Run"
  echo "═══════════════════════════════════════════════════"

  gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --region "$REGION" \
    --allow-unauthenticated \
    --no-cpu-throttling \
    --set-env-vars "STORAGE_BACKEND=firestore,ENV=production,CORS_ORIGINS=$CORS_ORIGIN" \
    --update-secrets "GOOGLE_API_KEY=GOOGLE_API_KEY:latest,GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID:latest,GOOGLE_CLIENT_SECRET=GOOGLE_CLIENT_SECRET:latest,JWT_SECRET=JWT_SECRET:latest" \
    --min-instances=0 \
    --max-instances=2 \
    --memory=512Mi

  echo ""
  echo "✅ Backend deployed."
  echo ""
fi

# ─── Frontend: Firebase Hosting ──────────────────────────────────────────────
if [ "$FRONTEND" = true ]; then
  echo "═══════════════════════════════════════════════════"
  echo "  🌐 Building & Deploying Frontend"
  echo "═══════════════════════════════════════════════════"

  # Build Vue app
  echo "📦 Building frontend..."
  (cd web && npm run build)

  # Deploy hosting + Firestore rules
  echo "🔥 Deploying to Firebase Hosting..."
  firebase deploy --only hosting,firestore:rules

  echo ""
  echo "✅ Frontend deployed to https://${FIREBASE_SITE}.web.app"
  echo ""
fi

echo "═══════════════════════════════════════════════════"
echo "  🎉 Deployment Complete!"
echo "═══════════════════════════════════════════════════"
