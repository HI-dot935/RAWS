FROM python:3.11-slim

# System deps: weasyprint needs pango/cairo, exiftool-ish libs handled by Pillow/pypdf natively
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY frontend ./frontend

RUN mkdir -p /data
VOLUME ["/data"]

ENV OSINT_DB_PATH=/data/cases.db
ENV PYTHONUNBUFFERED=1

EXPOSE 8420

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8420"]
