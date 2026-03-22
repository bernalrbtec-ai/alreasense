"""
Celery application for alrea_sense.

Worker: celery -A alrea_sense worker -l info -Q celery
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alrea_sense.settings")

app = Celery("alrea_sense")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
