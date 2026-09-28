FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# IMPORTANT: dockerContext must be SOFTWARE/backend (Render Settings + render.yaml).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Includes Prirucnici/ → /app/Prirucnici for startup restore.

RUN chmod +x scripts/start.sh

EXPOSE 8000

CMD ["./scripts/start.sh"]
