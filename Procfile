web: cd backend && python manage.py migrate --fake-initial && python create_superuser.py && daphne -b 0.0.0.0 -p $PORT alrea_sense.asgi:application
worker: cd backend && celery -A alrea_sense worker -l info
beat: cd backend && celery -A alrea_sense beat -l info

