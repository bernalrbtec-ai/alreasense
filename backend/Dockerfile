FROM python:3.11-slim

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
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Create staticfiles directory
RUN mkdir -p /app/staticfiles

# Collect static files
RUN python manage.py collectstatic --noinput --clear

# Expose port
EXPOSE 8000

# Default command
CMD ["sh", "-c", "python fix_tenant_migration.py && python manage.py fix_evolution_table && python clean_corrupted_encrypted_data.py && python manage.py migrate && python create_superuser.py && python ensure_plan_table.py && python seed_plans.py && python check_user_permissions.py && daphne -b 0.0.0.0 -p 8000 alrea_sense.asgi:application"]
