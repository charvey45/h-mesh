FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir paho-mqtt==2.1.0

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY config /app/config
COPY docker /app/docker

ENV PYTHONPATH=/app/src
