# Generated migration for RedisUsageSample (idempotent: IF NOT EXISTS)

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
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
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    CREATE TABLE IF NOT EXISTS servicos_redisusagesample (
                        id BIGSERIAL PRIMARY KEY,
                        sampled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        used_memory BIGINT NOT NULL,
                        aof_current_size BIGINT
                    );
                    """,
                    reverse_sql="DROP TABLE IF EXISTS servicos_redisusagesample;",
                ),
                migrations.RunSQL(
                    sql="CREATE INDEX IF NOT EXISTS idx_servicos_redisusagesample_sampled_at ON servicos_redisusagesample(sampled_at DESC);",
                    reverse_sql="DROP INDEX IF EXISTS idx_servicos_redisusagesample_sampled_at;",
                ),
            ],
        ),
    ]
