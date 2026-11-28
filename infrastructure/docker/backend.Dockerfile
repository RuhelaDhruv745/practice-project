# Backend API image (FastAPI + policy_engine + ai_engine).
# Build from the repo root:  docker build -f infrastructure/docker/backend.Dockerfile .
# Secrets (ANTHROPIC_API_KEY, GROQ_API_KEY) are supplied at runtime only; none are
# copied into this image (.dockerignore excludes .env).

# ---- builder: install Python dependencies into an isolated virtualenv ----
FROM python:3.13-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY contracts/requirements.txt contracts/requirements.txt
COPY policy_engine/requirements.txt policy_engine/requirements.txt
COPY ai_engine/requirements.txt ai_engine/requirements.txt
COPY backend/requirements.txt backend/requirements.txt
RUN pip install \
        -r contracts/requirements.txt \
        -r policy_engine/requirements.txt \
        -r ai_engine/requirements.txt \
        -r backend/requirements.txt

# ---- runtime: slim image, non-root user, no build tooling ----
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    LLM_PROVIDER=mock \
    DATABASE_URL=sqlite:////app/outputs/app.db \
    LOG_LEVEL=INFO

RUN groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid appuser --home-dir /home/appuser \
       --create-home --shell /usr/sbin/nologin appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY contracts/ contracts/
COPY policy_engine/ policy_engine/
COPY ai_engine/ ai_engine/
COPY backend/ backend/
# Policy YAML, campaigns (if any) and the synthetic seed CSV. data/fixtures is
# excluded by .dockerignore (test-only).
COPY data/ data/

# SQLite database, mock outbox and audit exports live here (mount a volume).
RUN mkdir -p /app/outputs && chown appuser:appuser /app/outputs
VOLUME ["/app/outputs"]

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"]

# Seeding is idempotent (upsert), so it is safe on every start. uvicorn's own access
# log is off: the backend's request-logging middleware (logger backend.access) already
# logs every request, redacted.
CMD ["sh", "-c", "python -m backend.app.seed && exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --no-access-log"]
