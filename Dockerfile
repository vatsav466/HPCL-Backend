# syntax=docker/dockerfile:1

# ---------- Stage 1: Build dependencies ----------
FROM python:3.12-slim AS builder

WORKDIR /app

# System deps needed to build some Python wheels (psycopg2, cx_Oracle etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    # Pin setuptools below 82 — newer setuptools dropped pkg_resources,
    # which breaks the legacy build of cx_Oracle 8.3.0 on Python 3.12.
    && pip install --user "setuptools<82" \
    && pip install --user --no-cache-dir -r requirements.txt


# ---------- Stage 2: Runtime image ----------
FROM python:3.12-slim

WORKDIR /app

# Create a non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Runtime-only system deps (no compilers in final image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    unixodbc \
    && rm -rf /var/lib/apt/lists/*

# Bring in the packages installed in the builder stage
COPY --from=builder /root/.local /home/appuser/.local
COPY . .

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8000

# Healthcheck hits your API's /health endpoint — adjust path if different
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

# --- Choose ONE of the following CMDs depending on your framework ---

# FastAPI (uvicorn + gunicorn worker manager) - recommended for production
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "60"]

# Flask (uncomment if using Flask instead)
# CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000", "--workers", "4"]

# Django (uncomment if using Django instead)
# CMD ["gunicorn", "project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
