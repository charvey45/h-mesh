FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir paho-mqtt==2.1.0

COPY docker/integration/endpoint.py /app/endpoint.py

ENTRYPOINT ["python", "/app/endpoint.py"]
