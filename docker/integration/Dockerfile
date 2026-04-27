# This image is used by the pi->mqtt->pi integration harness. It includes the integration
# fixtures and config examples in addition to the runtime source tree.
FROM python:3.11-slim

WORKDIR /app

# Keep the runtime dependency list intentionally tiny for repeatable lab runs.
RUN pip install --no-cache-dir paho-mqtt==2.1.0

# The integration image needs the source tree, the example configs, and the docker fixture payloads.
COPY pyproject.toml README.md /app/
COPY src /app/src
COPY config /app/config
COPY docker /app/docker

ENV PYTHONPATH=/app/src
