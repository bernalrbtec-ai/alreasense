# Generated migration - tabelas criadas via SQL em scripts/sql/proxy_rotation_tables.sql
# Rodar: python manage.py migrate proxy --fake-initial (após executar o SQL)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProxyRotationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('running', 'Em execução'), ('success', 'Sucesso'), ('partial', 'Parcial'), ('failed', 'Falhou')], default='running', max_length=20)),
                ('num_proxies', models.IntegerField(default=0)),
                ('num_instances', models.IntegerField(default=0)),
                ('num_updated', models.IntegerField(default=0)),
                ('strategy', models.CharField(choices=[('rotate', 'Rotate'), ('prioritize', 'Prioritize'), ('random', 'Random')], default='rotate', max_length=20)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('triggered_by', models.CharField(choices=[('manual', 'Manual'), ('n8n', 'n8n'), ('scheduled', 'Agendado')], default='manual', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='proxy_rotations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'proxy_proxyrotationlog',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ProxyRotationInstanceLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('instance_name', models.CharField(max_length=255)),
                ('proxy_host', models.CharField(max_length=255)),
                ('proxy_port', models.IntegerField()),
                ('success', models.BooleanField(default=False)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('rotation_log', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='instance_logs', to='proxy.proxyrotationlog')),
            ],
            options={
                'db_table': 'proxy_proxyrotationinstancelog',
                'ordering': ['rotation_log', 'instance_name'],
            },
        ),
    ]
