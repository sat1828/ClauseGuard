FROM python:3.11-slim

# tesseract-ocr: makes OCR fallback work out of the box in the container,
# instead of silently degrading to "ocr_unavailable" errors on every scanned PDF.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/storage/uploads

EXPOSE 8000

# --proxy-headers: this runs behind nginx in docker-compose, so trust the
# X-Forwarded-* headers nginx sets rather than seeing every request as
# coming from the nginx container's own IP.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
