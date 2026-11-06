FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv
COPY requirements.txt .
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
