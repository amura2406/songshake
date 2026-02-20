# syntax=docker/dockerfile:1
# -----------------------------------------------------------------
# Cloud Run image for Song Shake API
#
# Built REMOTELY by Cloud Build:
#   gcloud run deploy song-shake-api --source .
#
# No local Docker installation required.
# -----------------------------------------------------------------

FROM python:3.11-slim AS base

WORKDIR /app

# Install Python dependencies via pip (avoids uv lock file URL issues
# with Cloud Build's artifact-foundry-prod proxy returning 401).
COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[firebase]"

# Copy application source
COPY src/ ./src/

# Re-install the project itself (editable-like) so the package is importable
RUN pip install --no-cache-dir --no-deps .

# Cloud Run uses $PORT (default 8080)
ENV PORT=8080

EXPOSE 8080

CMD ["uvicorn", "song_shake.api:app", "--host", "0.0.0.0", "--port", "8080"]
