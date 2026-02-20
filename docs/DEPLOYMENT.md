# Deployment Guide

Song Shake runs on **Google Cloud Run** (backend) and **Firebase Hosting** (frontend).

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **Firebase project** linked to the GCP project
3. **gcloud CLI** authenticated (`gcloud auth login`)
4. **Firebase CLI** installed (`npm install -g firebase-tools`)
5. **Node.js 18+** for frontend build

## Secrets Setup (one-time)

Create the required Cloud Run secrets:

```bash
PROJECT_ID="your-gcp-project-id"

# Gemini API key
echo -n "your-gemini-api-key" | gcloud secrets create GOOGLE_API_KEY --data-file=- --project=$PROJECT_ID

# Google OAuth credentials
echo -n "your-client-id" | gcloud secrets create GOOGLE_CLIENT_ID --data-file=- --project=$PROJECT_ID
echo -n "your-client-secret" | gcloud secrets create GOOGLE_CLIENT_SECRET --data-file=- --project=$PROJECT_ID

# JWT secret for sessions
echo -n "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" | \
  gcloud secrets create JWT_SECRET --data-file=- --project=$PROJECT_ID
```

Grant the Cloud Run service account access:

```bash
SA="$(gcloud iam service-accounts list --filter='displayName:Compute Engine' --format='value(email)' --project=$PROJECT_ID)"
for SECRET in GOOGLE_API_KEY GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET JWT_SECRET; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID
done
```

## Deploy

### Using the deploy script (recommended)

```bash
# Full deploy: build frontend → deploy backend → deploy hosting + rules
./deploy.sh

# Backend only
./deploy.sh --backend-only

# Frontend only (requires backend already deployed)
./deploy.sh --frontend-only
```

### Manual deploy

#### Backend (Cloud Run)

```bash
gcloud run deploy song-shake-api \
  --source . \
  --region asia-southeast2 \
  --allow-unauthenticated \
  --no-cpu-throttling \
  --set-env-vars "STORAGE_BACKEND=firestore,ENV=production,CORS_ORIGINS=https://your-firebase-domain.web.app" \
  --update-secrets "GOOGLE_API_KEY=GOOGLE_API_KEY:latest,GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID:latest,GOOGLE_CLIENT_SECRET=GOOGLE_CLIENT_SECRET:latest,JWT_SECRET=JWT_SECRET:latest" \
  --min-instances=0 \
  --max-instances=2 \
  --memory=512Mi
```

#### Frontend (Firebase Hosting)

```bash
cd web
npm run build
cd ..
firebase deploy --only hosting,firestore:rules
```

## Environment Variables (Cloud Run)

| Variable | Value |
|----------|-------|
| `STORAGE_BACKEND` | `firestore` |
| `ENV` | `production` |
| `CORS_ORIGINS` | Your Firebase Hosting URL |

All secrets (`GOOGLE_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `JWT_SECRET`) are injected via Cloud Run secrets.

## Local Development with Firestore

By default, the backend uses **TinyDB** (local JSON file). To test against the production Firestore database locally:

### 1. Authenticate with Google Cloud

```bash
gcloud auth application-default login --project your-project-id
```

### 2. Set environment variables in `.env`

```bash
STORAGE_BACKEND=firestore
GOOGLE_CLOUD_PROJECT=your-project-id   # Required for ADC to find the right project
```

### 3. Start the backend

```bash
uv run uvicorn song_shake.api:app --reload --port 8000
```

> [!WARNING]
> This connects to the **real production Firestore** database. Any writes (enrichments, wipes) affect production data.

### Switching back to TinyDB

Remove or change `STORAGE_BACKEND` in `.env`:

```bash
STORAGE_BACKEND=tinydb   # or remove the line entirely
```

No cloud credentials are needed for TinyDB mode.

## Post-Deploy Checklist

- [ ] Verify Cloud Run service is `Serving`
- [ ] Check Firebase Hosting serves the frontend
- [ ] Test Google OAuth login (redirect URI must match)
- [ ] Run a playlist enrichment
- [ ] Verify Firestore has data
