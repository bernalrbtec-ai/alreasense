FROM python:3.11-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
        libpq-dev \
        curl \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy project
COPY backend/ /app/

# Configure entrypoint script
RUN chmod +x /app/entrypoint.sh

# Create staticfiles directory
RUN mkdir -p /app/staticfiles

# ✅ REMOVIDO: collectstatic do Dockerfile - será executado no Procfile durante deploy
# Isso evita duplicação e permite que seja executado apenas quando necessário

# Expose port
EXPOSE 8000

# Default command
CMD ["/app/entrypoint.sh"]
