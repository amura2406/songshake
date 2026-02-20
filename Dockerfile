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

# Install uv for fast Python dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install Python dependencies (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra firebase

# Copy application source
COPY src/ ./src/

# Cloud Run uses $PORT (default 8080)
ENV PORT=8080

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "song_shake.api:app", "--host", "0.0.0.0", "--port", "8080"]
