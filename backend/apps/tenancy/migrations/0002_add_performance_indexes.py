# Índices e schema já aplicados em tenancy_schema.sql (0001). Este migration é no-op para manter o histórico.

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0001_initial")]

    operations = [
        migrations.RunSQL(sql="SELECT 1", reverse_sql=migrations.RunSQL.noop),
    ]
