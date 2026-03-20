"""
Modelos para log de rotação de proxies (Webshare → Evolution API).
"""
from django.conf import settings
from django.db import models


class ProxyRotationLog(models.Model):
    """Registro de cada execução de rotação."""

    STATUS_CHOICES = [
        ('running', 'Em execução'),
        ('success', 'Sucesso'),
        ('partial', 'Parcial'),
        ('failed', 'Falhou'),
    ]
    TRIGGERED_CHOICES = [
        ('manual', 'Manual'),
        ('n8n', 'n8n'),
        ('scheduled', 'Agendado'),
    ]
    STRATEGY_CHOICES = [
        ('rotate', 'Rotate'),
        ('prioritize', 'Prioritize'),
        ('random', 'Random'),
    ]

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    num_proxies = models.IntegerField(default=0)
    num_instances = models.IntegerField(default=0)
    num_updated = models.IntegerField(default=0)
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES, default='rotate')
    error_message = models.TextField(null=True, blank=True)
    triggered_by = models.CharField(max_length=20, choices=TRIGGERED_CHOICES, default='manual')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proxy_rotations',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'proxy_proxyrotationlog'
        ordering = ['-created_at']

    def __str__(self):
        return f"ProxyRotation #{self.id} - {self.status} ({self.created_at})"


class ProxyRotationInstanceLog(models.Model):
    """Detalhe por instância em cada rotação."""

    rotation_log = models.ForeignKey(
        ProxyRotationLog,
        on_delete=models.CASCADE,
        related_name='instance_logs',
    )
    instance_name = models.CharField(max_length=255)
    proxy_host = models.CharField(max_length=255)
    proxy_port = models.IntegerField()
    success = models.BooleanField(default=False)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'proxy_proxyrotationinstancelog'
        ordering = ['rotation_log', 'instance_name']

    def __str__(self):
        return f"{self.instance_name} - {'OK' if self.success else 'FAIL'}"


class ProxyRotationSchedule(models.Model):
    """
    Agendamento de rotação automática (ex.: cron chama o comando que processa fila).
    """

    STRATEGY_CHOICES = ProxyRotationLog.STRATEGY_CHOICES

    name = models.CharField(max_length=120, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    interval_minutes = models.PositiveIntegerField(
        default=1440,
        help_text="Intervalo entre execuções (minutos). Ex.: 1440 = uma vez por dia.",
    )
    strategy = models.CharField(
        max_length=20,
        choices=STRATEGY_CHOICES,
        default="rotate",
    )
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proxy_rotation_schedules",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "proxy_proxyrotationschedule"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "next_run_at"]),
        ]

    def __str__(self):
        label = self.name.strip() or f"Agendamento #{self.pk}"
        return f"{label} ({self.interval_minutes} min)"
