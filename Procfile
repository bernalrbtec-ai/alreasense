web: cd backend && echo "🚀 [DEPLOY] Iniciando deploy..." && echo "📦 [DEPLOY] Executando migrações..." && timeout 300 python manage.py migrate --fake-initial && echo "✅ [DEPLOY] Migrações concluídas!" && echo "👤 [DEPLOY] Criando superuser..." && timeout 60 python create_superuser.py && echo "✅ [DEPLOY] Superuser criado!" && echo "🌐 [DEPLOY] Iniciando servidor Daphne..." && daphne -b 0.0.0.0 -p $PORT alrea_sense.asgi:application
worker: cd backend && echo "🔄 [WORKER] Iniciando Celery Worker..." && celery -A alrea_sense worker -l info
beat: cd backend && echo "⏰ [BEAT] Iniciando Celery Beat..." && celery -A alrea_sense beat -l info

