"""
Modelos para serviços (limpeza Redis, etc.).
"""
from django.conf import settings
from django.db import models


class RedisCleanupLog(models.Model):
    """Registro de cada execução de limpeza Redis."""

    STATUS_CHOICES = [
        ("running", "Em execução"),
        ("success", "Sucesso"),
        ("failed", "Falhou"),
    ]
    TRIGGERED_CHOICES = [
        ("manual", "Manual"),
        ("scheduled", "Agendado"),
    ]

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="running")
    keys_deleted_profile_pic = models.IntegerField(default=0)
    keys_deleted_webhook = models.IntegerField(default=0)
    bytes_freed_estimate = models.BigIntegerField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    triggered_by = models.CharField(max_length=20, choices=TRIGGERED_CHOICES, default="manual")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="redis_cleanup_logs",
    )
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "servicos_rediscleanuplog"
        ordering = ["-started_at"]

    def __str__(self):
        return f"RedisCleanup #{self.id} - {self.status} ({self.started_at})"
