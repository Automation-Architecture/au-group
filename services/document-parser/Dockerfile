# Container image for BOTH the EC2/ECS path AND Railway.
#
# This file is NOT optional and Railway does NOT use nixpacks here — verified from
# Railway build logs on 2026-08-13, which execute these exact steps. All four Railway
# services (au-group, pipeline-worker, daily-report, intake-cron) build from this
# Dockerfile, so `nixpacks.toml` is effectively dead config.
#
# Consequence: anything the cron services import MUST be COPYed below. Copying only
# `app` shipped an image with no `pipeline` package, so `python -m pipeline.worker`
# died on `ModuleNotFoundError: No module named 'pipeline'` on every scheduled run.
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
# Required by the three Railway cron services (pipeline-worker / daily-report /
# intake-cron), which start with `python -m pipeline.<module>`. Without this the
# image has no `pipeline` package and every scheduled run dies on import.
COPY pipeline ./pipeline

ENV PORT=8001
EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
