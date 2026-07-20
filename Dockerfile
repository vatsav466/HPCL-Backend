FROM python:3.11-slim AS base

# Build deps for python-ldap and similar native packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    libldap2-dev libsasl2-dev libssl-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
