"""
URLs do app servicos (Redis overview, limpeza, histórico).
"""
from django.urls import path

from . import views

urlpatterns = [
    path("redis/overview/", views.redis_overview),
    path("redis/statistics/", views.redis_statistics),
    path("redis/cleanup-history/", views.redis_cleanup_history),
    path("redis/metrics/", views.redis_metrics),
    path("redis/cleanup/", views.redis_cleanup),
]
