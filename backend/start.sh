#!/bin/bash

# Debug environment variables
echo "=== Environment Variables ==="
echo "DATABASE_URL: $DATABASE_URL"
echo "DEBUG: $DEBUG"
echo "ALLOWED_HOSTS: $ALLOWED_HOSTS"
echo "============================="

# Test database connection
echo "Testing database connection..."
python manage.py dbshell --command="SELECT version();" || echo "Database connection failed"

# Wait for database to be ready
echo "Waiting for database..."
python manage.py migrate --check
while [ $? -ne 0 ]; do
    echo "Database not ready, waiting..."
    sleep 2
    python manage.py migrate --check
done

# Preserve WhatsApp Instances before migrations
echo "Preserving WhatsApp Instances..."
python preserve_whatsapp_instances.py

# Run migrations
echo "Running migrations..."
python manage.py migrate

# Restore WhatsApp Instances after migrations
echo "Restoring WhatsApp Instances..."
python preserve_whatsapp_instances.py restore

# Create superuser
echo "Creating superuser..."
python create_superuser.py

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start the server
echo "Starting server..."
exec daphne -b 0.0.0.0 -p $PORT alrea_sense.asgi:application
