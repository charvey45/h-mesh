# This image packages the Python gateway code plus example config so the dashboard and
# demo sensor processes can run in Docker without a separate install step.
FROM python:3.11-slim

# Keep the container layout simple and predictable.
WORKDIR /app

# Only paho-mqtt is needed at runtime for the current scaffold commands.
RUN pip install --no-cache-dir paho-mqtt==2.1.0

# Copy the project metadata, example config, and source tree used by the CLI commands.
COPY pyproject.toml README.md /app/
COPY config /app/config
COPY src /app/src

# Let `python -m h_mesh_gateway ...` resolve the local source tree directly.
ENV PYTHONPATH=/app/src
