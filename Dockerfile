FROM python:3.12-slim

# Install system dependencies for voice (ffmpeg, opus)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libopus0 git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency file first for layer caching
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy application code
COPY . .

# Run database migrations on startup, then start the bot
CMD alembic upgrade head && python -m bot.main
