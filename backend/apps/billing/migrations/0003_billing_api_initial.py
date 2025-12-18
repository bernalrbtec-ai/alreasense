# Generated migration for billing_api_initial

from django.db import migrations
import os


def load_sql_file():
    """Carrega arquivo SQL"""
    file_path = os.path.join(os.path.dirname(__file__), '0003_billing_api_initial.sql')
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0002_initial'),  # Ajustar conforme última migration existente
        ('campaigns', '__latest__'),  # Usar a última migration de campaigns
        ('tenancy', '__latest__'),  # Usar a última migration de tenancy
    ]

    operations = [
        migrations.RunSQL(
            sql=load_sql_file(),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

