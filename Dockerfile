FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SCRAPLING_EXECUTABLE_PATH=/usr/bin/chromium

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

# Create runtime folders
RUN mkdir -p /app/tmp/uploads /app/logs

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Create unprivileged user and use it
RUN useradd --system --no-create-home botuser || true
USER botuser

ENTRYPOINT ["/app/entrypoint.sh"]
