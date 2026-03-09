# Generated migration for RedisUsageSample

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="RedisUsageSample",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sampled_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("used_memory", models.BigIntegerField()),
                ("aof_current_size", models.BigIntegerField(blank=True, null=True)),
            ],
            options={
                "db_table": "servicos_redisusagesample",
                "ordering": ["-sampled_at"],
            },
        ),
    ]
