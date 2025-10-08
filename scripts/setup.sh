#!/bin/bash

# EvoSense Setup Script
# This script sets up the development environment

set -e

echo "🚀 Setting up EvoSense development environment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

print_status "Docker and Docker Compose are installed ✓"

# Create .env files if they don't exist
if [ ! -f backend/.env ]; then
    print_status "Creating backend/.env from template..."
    cp backend/env.example backend/.env
    print_warning "Please edit backend/.env with your configuration"
fi

# Create frontend .env if it doesn't exist
if [ ! -f frontend/.env ]; then
    print_status "Creating frontend/.env..."
    cat > frontend/.env << EOF
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
EOF
fi

# Build and start services
print_status "Building and starting services..."
docker-compose up --build -d

# Wait for database to be ready
print_status "Waiting for database to be ready..."
sleep 10

# Run migrations
print_status "Running database migrations..."
docker-compose exec backend python manage.py migrate

# Create superuser
print_status "Creating superuser..."
docker-compose exec backend python manage.py shell -c "
from django.contrib.auth import get_user_model
from apps.tenancy.models import Tenant

User = get_user_model()

# Create tenant
tenant, created = Tenant.objects.get_or_create(
    name='Demo Tenant',
    defaults={'plan': 'pro', 'status': 'active'}
)

# Create superuser
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser(
        username='admin',
        email='admin@evosense.com',
        password='admin123',
        tenant=tenant,
        role='admin'
    )
    print('Superuser created: admin/admin123')
else:
    print('Superuser already exists')
"

# Seed initial data
print_status "Seeding initial data..."
docker-compose exec backend python manage.py seed_data

print_status "Setup completed successfully! 🎉"
echo ""
echo "Access your application:"
echo "  Frontend: http://localhost:5173"
echo "  Backend API: http://localhost:8000"
echo "  Admin: http://localhost:8000/admin"
echo ""
echo "Login credentials:"
echo "  Username: admin"
echo "  Password: admin123"
echo ""
echo "To stop the services:"
echo "  docker-compose down"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
