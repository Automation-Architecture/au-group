# Optional container image for EC2/ECS deploy path (Railway uses nixpacks by default)
FROM python:3.11-slim-bookworm

# Apply security updates before adding OCR/poppler packages (Trivy OS scan).
RUN apt-get update \
    && apt-get -y upgrade --no-install-recommends \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        poppler-utils \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PORT=8001
EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
