FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    --default-timeout=300 \
    --retries=10 \
    -r requirements.txt

COPY . .

ENV PYTHONPATH=/app:/app/telemetry

RUN chmod +x entrypoint.sh

ENTRYPOINT ["/bin/sh", "entrypoint.sh"]

CMD ["python", "-u", "-m", "telemetry.app"]