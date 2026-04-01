# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxmlsec1-dev libxml2-dev pkg-config gcc \
    && rm -rf /var/lib/apt/lists/*

# ── dependencies layer ──────────────────────────────────────────────────────
FROM base AS deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── development image ────────────────────────────────────────────────────────
FROM deps AS development
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── production image ─────────────────────────────────────────────────────────
FROM deps AS production
ARG APP_VERSION=0.1.0
ARG BUILD_NUMBER=dev
ARG BUILD_DATE=unknown
ENV APP_VERSION=${APP_VERSION} \
    BUILD_NUMBER=${BUILD_NUMBER} \
    BUILD_DATE=${BUILD_DATE}
COPY . .
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser \
    && chmod +x /app/entrypoint.sh \
    && mkdir -p /var/lib/celerybeat \
    && chown appuser:appgroup /var/lib/celerybeat
USER appuser
# entrypoint.sh runs `alembic upgrade head` then starts uvicorn, ensuring
# the database schema is always up-to-date before traffic is accepted.
CMD ["/app/entrypoint.sh"]
