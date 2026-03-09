# Schema aplicado via script SQL (tenancy_schema.sql). Sem migrations .py para alterações de schema.

import uuid
from pathlib import Path

import django.db.models.deletion
from django.db import migrations, models


def read_schema_sql():
    path = Path(__file__).parent / "tenancy_schema.sql"
    return path.read_text(encoding="utf-8")


class Migration(migrations.Migration):
    initial = True
    dependencies = [("billing", "0001_initial")]

    operations = [
        migrations.RunSQL(
            sql=read_schema_sql(),
            reverse_sql=migrations.RunSQL.noop,
            state_operations=[
                migrations.CreateModel(
                    name="Tenant",
                    fields=[
                        ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ("name", models.CharField(max_length=160)),
                        ("status", models.CharField(choices=[("active", "Active"), ("suspended", "Suspended"), ("trial", "Trial")], default="active", max_length=16)),
                        ("next_billing_date", models.DateField(blank=True, null=True)),
                        ("ui_access", models.BooleanField(default=True, help_text="Tenant tem acesso à UI (ex: API Only = False)")),
                        ("allow_meta_interactive_buttons", models.BooleanField(default=True, help_text="Permite envio de mensagens com reply buttons (Meta, janela 24h). Desative para desabilitar a feature por tenant.")),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        ("current_plan", models.ForeignKey(blank=True, help_text="Plano atual do tenant", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tenants", to="billing.plan")),
                    ],
                    options={"db_table": "tenancy_tenant", "verbose_name": "Tenant", "verbose_name_plural": "Tenants"},
                ),
            ],
        ),
    ]
