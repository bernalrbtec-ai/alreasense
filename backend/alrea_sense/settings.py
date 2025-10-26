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
# ✅ SECURITY FIX: Use insecure default only for build time (collectstatic)
# Railway will use the real SECRET_KEY from env vars at runtime
SECRET_KEY = config('SECRET_KEY', default='django-insecure-build-time-only-do-not-use-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
# ✅ IMPROVEMENT: DEBUG should default to False for security
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,alreasense-production.up.railway.app,alreasense-backend-production.up.railway.app').split(',')

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
    'apps.chat',  # Flow Chat
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
    # ✅ IMPROVEMENT: Security and performance middlewares
    'apps.common.security_middleware.SecurityAuditMiddleware',
    'apps.common.performance_middleware.PerformanceMiddleware',
    # 'apps.common.performance_middleware.DatabaseQueryCountMiddleware',  # Only for DEBUG
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

# ✅ IMPROVEMENT: Database connection pooling and performance
DATABASES['default']['CONN_MAX_AGE'] = config('DB_CONN_MAX_AGE', default=600, cast=int)  # 10 minutes
DATABASES['default']['OPTIONS'] = {
    'connect_timeout': 10,
    'options': '-c statement_timeout=30000'  # 30 seconds query timeout
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

# Upload/Request Settings
# Aumentado para suportar webhooks do Evolution com mídia em base64
DATA_UPLOAD_MAX_MEMORY_SIZE = config('DATA_UPLOAD_MAX_MEMORY_SIZE', default=52428800, cast=int)  # 50MB
FILE_UPLOAD_MAX_MEMORY_SIZE = config('FILE_UPLOAD_MAX_MEMORY_SIZE', default=52428800, cast=int)  # 50MB

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
    'PAGE_SIZE_MAX': 10000,  # Permitir até 10.000 itens por página
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

# Debug CORS configuration (only in DEBUG mode)
if DEBUG:
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"CORS_ALLOWED_ORIGINS: {CORS_ALLOWED_ORIGINS}")

CORS_ALLOW_CREDENTIALS = True
# ✅ SECURITY FIX: Never allow all origins in production
CORS_ALLOW_ALL_ORIGINS = False

# Force CORS headers to be added to all responses
CORS_PREFLIGHT_MAX_AGE = 86400

# Additional CORS settings for Railway
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

# Ensure CORS headers are always present
CORS_EXPOSE_HEADERS = ['content-type', 'x-requested-with']

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

# Redis - Railway Configuration
REDIS_URL = config('REDIS_URL', default='')
REDIS_PASSWORD = config('REDISPASSWORD', default='')
REDIS_HOST = config('REDISHOST', default='localhost')
REDIS_PORT = config('REDISPORT', default='6379')
REDIS_USER = config('REDISUSER', default='default')

# Debug das variáveis de ambiente
print(f"🔍 [DEBUG] REDIS_URL env: {os.environ.get('REDIS_URL', 'Not set')}")
print(f"🔍 [DEBUG] REDISHOST env: {os.environ.get('REDISHOST', 'Not set')}")
print(f"🔍 [DEBUG] REDISPASSWORD env: {'Set' if os.environ.get('REDISPASSWORD') else 'Not set'}")

# Usar REDIS_URL se disponível, senão construir a partir das variáveis
if REDIS_URL and REDIS_URL != '':
    # Usar REDIS_URL diretamente do Railway
    print(f"✅ [REDIS] Usando REDIS_URL diretamente")
    
    # Extrair informações da REDIS_URL para as variáveis individuais
    try:
        from urllib.parse import urlparse
        parsed = urlparse(REDIS_URL)
        if parsed.hostname:
            REDIS_HOST = parsed.hostname
        if parsed.port:
            REDIS_PORT = str(parsed.port)
        if parsed.username:
            REDIS_USER = parsed.username
        if parsed.password:
            REDIS_PASSWORD = parsed.password
        print(f"🔧 [REDIS] Extraído da URL - Host: {REDIS_HOST}, Port: {REDIS_PORT}, User: {REDIS_USER}")
    except Exception as e:
        print(f"⚠️ [REDIS] Erro ao extrair info da URL: {e}")
        
else:
    # Construir URL do Redis a partir das variáveis individuais
    if REDIS_HOST and REDIS_HOST != 'localhost':
        if REDIS_PASSWORD:
            REDIS_URL = f"redis://{REDIS_USER}:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
            print(f"✅ [REDIS] Construindo URL com password")
        else:
            REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
            print(f"✅ [REDIS] Construindo URL sem password")
    else:
        # Se não conseguir construir a URL, usar fallback localhost apenas em DEBUG
        if DEBUG:
            REDIS_URL = 'redis://localhost:6379/0'
            print(f"⚠️ [REDIS] Usando localhost como fallback (DEBUG mode)")
        else:
            REDIS_URL = ''
            print(f"❌ [REDIS] Erro: Redis não configurado em produção!")

print(f"🔧 [SETTINGS] REDIS_URL: {REDIS_URL[:50]}..." if REDIS_URL else "🔧 [SETTINGS] REDIS_URL: Not configured...")
print(f"🔧 [SETTINGS] REDIS_HOST: {REDIS_HOST}")
print(f"🔧 [SETTINGS] REDIS_PORT: {REDIS_PORT}")
print(f"🔧 [SETTINGS] REDIS_USER: {REDIS_USER}")
print(f"🔧 [SETTINGS] REDIS_PASSWORD: {'Set' if REDIS_PASSWORD else 'Not set'}")

# Channels - Using Redis URL
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [REDIS_URL.replace('/0', '/1') if REDIS_URL else 'redis://localhost:6379/1'],
        },
    },
}

# RabbitMQ - Railway Configuration
# ✅ IMPROVEMENT: Default for build time, real value from env at runtime
RABBITMQ_URL = config('RABBITMQ_PRIVATE_URL', default='amqp://guest:guest@localhost:5672/')

print(f"🔧 [SETTINGS] RABBITMQ_URL: {RABBITMQ_URL[:50]}...")

# MongoDB removido - usando PostgreSQL com pgvector

# Alertas por Email
ALERT_EMAIL_RECIPIENTS = config('ALERT_EMAIL_RECIPIENTS', default='', cast=lambda v: [s.strip() for s in v.split(',') if s.strip()])

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
# ✅ IMPROVEMENT: Default for build time, real value from env at runtime
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
        # Logger específico para chat (webhook) - menos verboso em produção
        'apps.chat': {
            'handlers': ['console'],
            'level': config('CHAT_LOG_LEVEL', default='WARNING'),  # WARNING em prod, INFO em dev
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

# ============================
# FLOW CHAT - Storage Configuration
# ============================

# Local storage (Railway Volume) para cache quente
CHAT_LOCAL_STORAGE_PATH = config('CHAT_LOCAL_STORAGE_PATH', default='/mnt/storage/whatsapp/')

# MinIO (S3-compatible) para storage definitivo
S3_BUCKET = config('S3_BUCKET', default='flow-attachments')
S3_ENDPOINT_URL = config('S3_ENDPOINT_URL', default='https://bucket-production-8fb1.up.railway.app')
# ✅ IMPROVEMENT: Empty defaults for build time, real values from env at runtime
S3_ACCESS_KEY = config('S3_ACCESS_KEY', default='')
S3_SECRET_KEY = config('S3_SECRET_KEY', default='')
S3_REGION = config('S3_REGION', default='us-east-1')

# Debug settings for Railway deploy - AFTER all configurations are loaded
print("🚀 [SETTINGS] ==========================================")
print("🚀 [SETTINGS] DJANGO SETTINGS LOADED SUCCESSFULLY!")
print("🚀 [SETTINGS] ==========================================")
print(f"🔧 [SETTINGS] DEBUG: {DEBUG}")
print(f"🔧 [SETTINGS] ALLOWED_HOSTS: {ALLOWED_HOSTS}")
print(f"🔧 [SETTINGS] DATABASE: {DATABASES['default']['ENGINE']}")
print(f"🔧 [SETTINGS] REDIS_URL: {REDIS_URL[:20] if REDIS_URL else 'Not configured'}...")
print(f"🔧 [SETTINGS] REDIS_HOST: {REDIS_HOST}")
print(f"🔧 [SETTINGS] REDIS_PORT: {REDIS_PORT}")
print(f"🔧 [SETTINGS] REDIS_USER: {REDIS_USER}")
print(f"🔧 [SETTINGS] REDIS_PASSWORD: {'***' if REDIS_PASSWORD else 'Not set'}")
print(f"🔧 [SETTINGS] PAGE_SIZE: {REST_FRAMEWORK['PAGE_SIZE']}")
print(f"🔧 [SETTINGS] PAGE_SIZE_MAX: {REST_FRAMEWORK.get('PAGE_SIZE_MAX', 'Not set')}")
print(f"🔧 [SETTINGS] INSTALLED_APPS: {len(INSTALLED_APPS)} apps")

# Log application loading
print(f"📱 [APPS] Loading {len(LOCAL_APPS)} local apps: {', '.join([app.split('.')[-1] for app in LOCAL_APPS])}")
print(f"📱 [APPS] Loading {len(THIRD_PARTY_APPS)} third-party apps: {', '.join([app.split('.')[-1] for app in THIRD_PARTY_APPS])}")
print(f"📱 [APPS] Total apps: {len(INSTALLED_APPS)}")

# Log middleware
print(f"🔧 [MIDDLEWARE] Loading {len(MIDDLEWARE)} middleware components")
print(f"🔧 [MIDDLEWARE] Components: {', '.join(MIDDLEWARE)}")

print("✅ [SETTINGS] All configurations loaded successfully!")
print("🚀 [SETTINGS] Ready for deployment!")
