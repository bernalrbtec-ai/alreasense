# Generated manually for ProxyRotationSchedule

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("proxy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProxyRotationSchedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, default="", max_length=120)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                (
                    "interval_minutes",
                    models.PositiveIntegerField(
                        default=1440,
                        help_text="Intervalo entre execuções (minutos). Ex.: 1440 = uma vez por dia.",
                    ),
                ),
                (
                    "strategy",
                    models.CharField(
                        choices=[("rotate", "Rotate"), ("prioritize", "Prioritize"), ("random", "Random")],
                        default="rotate",
                        max_length=20,
                    ),
                ),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("next_run_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="proxy_rotation_schedules",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "proxy_proxyrotationschedule",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="proxyrotationschedule",
            index=models.Index(fields=["is_active", "next_run_at"]),
        ),
    ]
