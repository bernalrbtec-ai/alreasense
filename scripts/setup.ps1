# EvoSense Setup Script for Windows
# This script sets up the development environment

Write-Host "🚀 Setting up EvoSense development environment..." -ForegroundColor Green

# Check if Docker is installed
try {
    docker --version | Out-Null
    Write-Host "[INFO] Docker is installed ✓" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Docker is not installed. Please install Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if Docker Compose is installed
try {
    docker-compose --version | Out-Null
    Write-Host "[INFO] Docker Compose is installed ✓" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Docker Compose is not installed. Please install Docker Compose first." -ForegroundColor Red
    exit 1
}

# Create .env files if they don't exist
if (-not (Test-Path "backend\.env")) {
    Write-Host "[INFO] Creating backend\.env from template..." -ForegroundColor Green
    Copy-Item "backend\env.example" "backend\.env"
    Write-Host "[WARNING] Please edit backend\.env with your configuration" -ForegroundColor Yellow
}

# Create frontend .env if it doesn't exist
if (-not (Test-Path "frontend\.env")) {
    Write-Host "[INFO] Creating frontend\.env..." -ForegroundColor Green
    @"
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
"@ | Out-File -FilePath "frontend\.env" -Encoding UTF8
}

# Build and start services
Write-Host "[INFO] Building and starting services..." -ForegroundColor Green
docker-compose up --build -d

# Wait for database to be ready
Write-Host "[INFO] Waiting for database to be ready..." -ForegroundColor Green
Start-Sleep -Seconds 10

# Run migrations
Write-Host "[INFO] Running database migrations..." -ForegroundColor Green
docker-compose exec backend python manage.py migrate

# Create superuser
Write-Host "[INFO] Creating superuser..." -ForegroundColor Green
docker-compose exec backend python manage.py shell -c @"
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
"@

# Seed initial data
Write-Host "[INFO] Seeding initial data..." -ForegroundColor Green
docker-compose exec backend python manage.py seed_data

Write-Host "[INFO] Setup completed successfully! 🎉" -ForegroundColor Green
Write-Host ""
Write-Host "Access your application:" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  Backend API: http://localhost:8000" -ForegroundColor White
Write-Host "  Admin: http://localhost:8000/admin" -ForegroundColor White
Write-Host ""
Write-Host "Login credentials:" -ForegroundColor Cyan
Write-Host "  Username: admin" -ForegroundColor White
Write-Host "  Password: admin123" -ForegroundColor White
Write-Host ""
Write-Host "To stop the services:" -ForegroundColor Cyan
Write-Host "  docker-compose down" -ForegroundColor White
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Cyan
Write-Host "  docker-compose logs -f" -ForegroundColor White
