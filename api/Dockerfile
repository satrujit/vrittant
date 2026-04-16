FROM python:3.12-slim

WORKDIR /app

# Install system deps for psycopg2 + curl_cffi (used by scrapling)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc libcurl4-openssl-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run sets PORT env var
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120 --preload"]
