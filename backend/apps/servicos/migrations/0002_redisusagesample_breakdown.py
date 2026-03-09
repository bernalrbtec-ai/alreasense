# Add breakdown fields to RedisUsageSample (idempotent: IF NOT EXISTS)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("servicos", "0001_redisusagesample"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="redisusagesample",
                    name="keys_profile_pic",
                    field=models.IntegerField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="redisusagesample",
                    name="keys_webhook",
                    field=models.IntegerField(blank=True, null=True),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    ALTER TABLE servicos_redisusagesample
                      ADD COLUMN IF NOT EXISTS keys_profile_pic INTEGER,
                      ADD COLUMN IF NOT EXISTS keys_webhook INTEGER;
                    """,
                    reverse_sql="""
                    ALTER TABLE servicos_redisusagesample
                      DROP COLUMN IF EXISTS keys_profile_pic,
                      DROP COLUMN IF EXISTS keys_webhook;
                    """,
                ),
            ],
        ),
    ]
