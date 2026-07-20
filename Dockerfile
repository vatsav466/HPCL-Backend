FROM python:3.12-slim

WORKDIR /app

# python-ldap needs these system headers/libs to compile from source —
# libsasl2-dev + libldap2-dev + libssl-dev are the actual build deps;
# gcc/build-essential provide the compiler itself.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
