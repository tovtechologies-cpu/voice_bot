FROM python:3.11-slim

WORKDIR /app

# System dependencies: ffmpeg for audio conversion, image libs for Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev libssl-dev libjpeg-dev zlib1g-dev ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ -r requirements.txt

# Copy application code
COPY backend/ .

# Create tickets directory
RUN mkdir -p /app/tickets

# Railway injects PORT env var — default to 8001
ENV PORT=8001

EXPOSE ${PORT}

CMD uvicorn server:app --host 0.0.0.0 --port ${PORT}
