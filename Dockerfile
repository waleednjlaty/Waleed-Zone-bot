FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SCRAPLING_EXECUTABLE_PATH=/usr/bin/chromium \
    HOME=/tmp/botuser \
    XDG_CACHE_HOME=/tmp/botuser/.cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    chromium \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install --no-cache-dir -r /app/requirements.txt

# Copy project files
COPY . /app

# Prepare writable runtime/cache folders for the unprivileged process.
RUN useradd --system --no-create-home botuser || true \
    && mkdir -p /app/data /app/tmp/uploads /app/logs /tmp/botuser/.cache \
    && chown -R botuser:nogroup /app/data /app/tmp /app/logs /tmp/botuser \
    && chmod +x /app/entrypoint.sh

USER botuser

ENTRYPOINT ["/app/entrypoint.sh"]
