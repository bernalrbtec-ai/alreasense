"""
Django settings for alrea_sense project.
"""

import os
from pathlib import Path
from decouple import config
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='N;.!iB5@sw?D2wJPr{Ysmt5][R%5.aHyAuvNpM_@DOb:OX*<.f')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'channels',
    'django_celery_beat',
]

LOCAL_APPS = [
    'apps.tenancy',
    'apps.authn',
    'apps.connections',
    'apps.ai',
    'apps.billing',
    'apps.chat_messages',
    'apps.experiments',
    'apps.notifications',
    'apps.contacts',
    'apps.campaigns',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.common.middleware.TenantMiddleware',
    # 'apps.common.webhook_debug_middleware.WebhookDebugMiddleware',  # Temporarily disabled
]

ROOT_URLCONF = 'alrea_sense.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'alrea_sense.wsgi.application'
ASGI_APPLICATION = 'alrea_sense.asgi.application'

# Database
DATABASES = {
    'default': dj_database_url.parse(
        config('DATABASE_URL', default='postgresql://postgres:postgres@localhost:5432/alrea_sense')
    )
}

# Custom User Model
AUTH_USER_MODEL = 'authn.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# URL Settings
APPEND_SLASH = False  # Disable automatic slash appending to prevent 301 redirects

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# STATICFILES_DIRS = [BASE_DIR / 'static']  # Disabled: directory doesn't exist

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Serve media files in production (Railway)
if not DEBUG:
    import os
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    # Exception for webhook endpoints
    'EXCEPTION_HANDLER': 'apps.common.exceptions.custom_exception_handler',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# JWT Settings
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
}

# CORS Settings - Hardcoded for Railway
CORS_ALLOWED_ORIGINS = [
    'http://localhost',
    'http://localhost:5173',
    'http://127.0.0.1',
    'http://127.0.0.1:5173',
    'https://alreasense-production.up.railway.app',
    'https://alreasense-backend-production.up.railway.app'
]

# Also try to get from environment variable as fallback
env_cors = config('CORS_ALLOWED_ORIGINS', default='')
if env_cors:
    for origin in env_cors.split(','):
        origin = origin.strip()
        if origin and origin not in CORS_ALLOWED_ORIGINS:
            CORS_ALLOWED_ORIGINS.append(origin)

# Debug CORS configuration
print(f"🌐 CORS_ALLOWED_ORIGINS: {CORS_ALLOWED_ORIGINS}")

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False  # Keep False for security, use CORS_ALLOWED_ORIGINS

# Force CORS headers to be added to all responses
CORS_PREFLIGHT_MAX_AGE = 86400

# Ensure CORS headers are always present
CORS_EXPOSE_HEADERS = ['content-type', 'x-requested-with']
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# CSRF Settings
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:5173,http://127.0.0.1:5173,https://alreasense-production.up.railway.app'
).split(',')

# CSRF exemption for webhook paths
CSRF_EXEMPT_PATHS = [
    '/webhooks/',
    '/api/health/',
]

# Channels
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [config('CHANNELS_REDIS_URL', default='redis://localhost:6379/1')],
        },
    },
}

# Celery
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Railway/Production Celery Settings
CELERY_WORKER_CONCURRENCY = 2  # Limit to 2 workers instead of 48
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Process one task at a time
CELERY_TASK_ACKS_LATE = True  # Acknowledge tasks after completion
CELERY_WORKER_MAX_TASKS_PER_CHILD = 50  # Restart worker after 50 tasks
CELERY_TASK_REJECT_ON_WORKER_LOST = True  # Reject tasks if worker dies
CELERY_WORKER_DISABLE_RATE_LIMITS = False  # Enable rate limits
CELERY_TASK_TIME_LIMIT = 300  # 5 minutes max per task
CELERY_TASK_SOFT_TIME_LIMIT = 240  # 4 minutes soft limit

# Celery Beat Schedule
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'check-campaign-health': {
        'task': 'apps.campaigns.tasks.check_campaign_health',
        'schedule': crontab(minute='*/5'),  # A cada 5 minutos
    },
}

# Stripe
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='')
STRIPE_PUBLISHABLE_KEY = config('STRIPE_PUBLISHABLE_KEY', default='')
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='')

# AI/N8N
N8N_AI_WEBHOOK = config('N8N_AI_WEBHOOK', default='')
AI_MODEL_NAME = config('AI_MODEL_NAME', default='qwen-local')
AI_EMBEDDING_MODEL = config('AI_EMBEDDING_MODEL', default='qwen-mini-embeddings')

# Evolution API (Consolidated)
EVOLUTION_API_URL = config('EVOLUTION_API_URL', default='https://evo.rbtec.com.br')
EVOLUTION_API_KEY = config('EVOLUTION_API_KEY', default='')

# Base URL for webhooks and callbacks
BASE_URL = config('BASE_URL', default='https://alreasense-backend-production.up.railway.app')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'format': '{"level": "%(levelname)s", "time": "%(asctime)s", "logger": "%(name)s", "message": "%(message)s"}',
        },
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json' if config('LOG_FORMAT', default='verbose') == 'json' else 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': config('LOG_LEVEL', default='INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
        'alrea_sense': {
            'handlers': ['console'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
    },
}

# Email
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@alreasense.com')

# Security
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Production Security Settings
# Only enable strict HTTPS in production with a reverse proxy (Railway)
IS_PRODUCTION = not DEBUG and config('RAILWAY_ENVIRONMENT', default='') == 'production'

if IS_PRODUCTION:
    # SSL/HTTPS Configuration
    SECURE_SSL_REDIRECT = True  # Redirect HTTP to HTTPS
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # Trust Railway proxy
    
    # HSTS Configuration
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Cookie Security
    SESSION_COOKIE_SECURE = True  # Only send session cookie over HTTPS
    CSRF_COOKIE_SECURE = True  # Only send CSRF cookie over HTTPS
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
    CSRF_COOKIE_HTTPONLY = True  # Prevent JavaScript access to CSRF cookie
    
    # Additional Security Headers
    SECURE_REFERRER_POLICY = 'same-origin'
