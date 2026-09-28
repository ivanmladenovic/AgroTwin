FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Build context is SOFTWARE/ (Render Blueprint dockerContext).
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
# Manuals: backend/Prirucnici → /app/Prirucnici

RUN chmod +x scripts/start.sh

EXPOSE 8000

CMD ["./scripts/start.sh"]
