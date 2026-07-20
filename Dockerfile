# syntax=docker/dockerfile:1

# ---------- Stage 1: Build dependencies ----------
FROM python:3.12-slim AS builder

WORKDIR /app

# System deps needed to build some Python wheels (psycopg2, cx_Oracle etc.)
# Note: python:3.12-slim is based on Debian, where the package is still
# named libaio1 (unlike Ubuntu 24.04 runners, which renamed it libaio1t64).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    unixodbc-dev \
    libaio1 \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# cx_Oracle has no prebuilt wheel for Python 3.12 on Linux, so pip builds it
# from source — that build needs the Oracle Instant Client headers/libs
# present at /opt/oracle, plus LD_LIBRARY_PATH set so it can link against them.
# Swap this whole block out if you migrate to `oracledb` (thin mode) instead —
# then none of this Instant Client setup is needed at all.
# NOTE: the zip extracts to a folder named instantclient_<version>, and that
# version changes as Oracle updates the "latest" download. We get the actual
# directory path and use it directly.
RUN mkdir -p /opt/oracle && cd /opt/oracle \
    && wget -q https://download.oracle.com/otn_software/linux/instantclient/instantclient-basiclite-linuxx64.zip \
    && unzip -q instantclient-basiclite-linuxx64.zip \
    && rm instantclient-basiclite-linuxx64.zip \
    && INSTALL_DIR=$(ls -d /opt/oracle/instantclient_* | head -n1) \
    && cd "$INSTALL_DIR" \
    && rm -f libclntsh.so libocci.so \
    && if ls libclntsh.so.* 1> /dev/null 2>&1; then ln -sf libclntsh.so.* libclntsh.so; fi \
    && if ls libocci.so.* 1> /dev/null 2>&1; then ln -sf libocci.so.* libocci.so; fi
# Create symlink at fixed path for environment variables
RUN rm -f /opt/oracle/instantclient && ln -sf /opt/oracle/instantclient_* /opt/oracle/instantclient
ENV LD_LIBRARY_PATH=/opt/oracle/instantclient:$LD_LIBRARY_PATH \
    OCI_LIB_DIR=/opt/oracle/instantclient \
    OCI_INC_DIR=/opt/oracle/instantclient/sdk/include

COPY requirements.txt .
RUN pip install --upgrade pip \
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