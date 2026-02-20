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
PROJECT_ID="songshake999"
BILLING_ACCOUNT="015067-7C1A56-0A678B"
BUDGET_DISPLAY_NAME="SongShake Monthly Budget"
BUDGET_AMOUNT="16000"

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

# ─── Cost Control: Budget Alert ──────────────────────────────────────────────
# Creates a $1/month budget with email alerts at 50%, 90%, 100%.
# Idempotent — skips if the budget already exists.
echo "═══════════════════════════════════════════════════"
echo "  💰 Ensuring Budget Alert"
echo "═══════════════════════════════════════════════════"

EXISTING_BUDGET=$(gcloud billing budgets list \
  --billing-account="$BILLING_ACCOUNT" \
  --filter="displayName='${BUDGET_DISPLAY_NAME}'" \
  --format="value(name)" 2>/dev/null || true)

if [ -n "$EXISTING_BUDGET" ]; then
  echo "✅ Budget '${BUDGET_DISPLAY_NAME}' already exists. Skipping."
else
  echo "📊 Creating ${BUDGET_AMOUNT} IDR/month budget with alerts at 50%, 90%, 100%..."
  gcloud billing budgets create \
    --billing-account="$BILLING_ACCOUNT" \
    --display-name="$BUDGET_DISPLAY_NAME" \
    --budget-amount="${BUDGET_AMOUNT}IDR" \
    --filter-projects="projects/507436470271" \
    --threshold-rule=percent=0.5 \
    --threshold-rule=percent=0.9 \
    --threshold-rule=percent=1.0
  echo "✅ Budget created. Alerts will be sent to your billing account email."
fi
echo ""

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
    --max-instances=1 \
    --memory=512Mi \
    --timeout=3600

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
