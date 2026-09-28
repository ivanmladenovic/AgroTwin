FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
# Bundle Agriser manuals so Render can restore PDFs after ephemeral disk resets.
COPY Prirucnici/ /app/Prirucnici/

RUN chmod +x scripts/start.sh

EXPOSE 8000

CMD ["./scripts/start.sh"]
