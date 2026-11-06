# syntax=docker/dockerfile:1
# The backend: the Python server, the face models and whisper.cpp. It serves the
# API on /api and the live stream on /ws. The web app is its own container
# (web/Dockerfile); docker-compose.yaml in the repo root starts both.
#   docker compose up -d --build

# pywhispercpp ships whisper.cpp ready-built for x86_64 and aarch64: no compiler needed
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv
COPY requirements.txt .
# a longer timeout: on a slow network a big wheel (OpenCV, whisper.cpp) can stall for a while
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 120 --retries 10 -r requirements.txt

COPY app ./app

# Never run a network service as root
RUN useradd --create-home --uid 1000 app \
 && mkdir -p /models /data && chown app /models /data
USER app

ENV BIND=0.0.0.0:8000 \
    MODEL_DIR=/models \
    DATA_DIR=/data \
    SPEECH=local
EXPOSE 8000
CMD ["python", "-m", "app"]
