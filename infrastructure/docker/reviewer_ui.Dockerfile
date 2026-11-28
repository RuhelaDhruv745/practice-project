# Streamlit reviewer UI image. Thin HTTP client of the backend; holds no secrets.
# Build from the repo root:  docker build -f infrastructure/docker/reviewer_ui.Dockerfile .

# ---- builder: install Python dependencies into an isolated virtualenv ----
FROM python:3.13-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY reviewer_ui/requirements.txt reviewer_ui/requirements.txt
RUN pip install -r reviewer_ui/requirements.txt

# ---- runtime ----
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    API_BASE_URL=http://backend:8000 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true

RUN groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid appuser --home-dir /home/appuser \
       --create-home --shell /usr/sbin/nologin appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY reviewer_ui/ reviewer_ui/

USER appuser
EXPOSE 8501

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4).status == 200 else 1)"]

CMD ["python", "-m", "streamlit", "run", "reviewer_ui/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
