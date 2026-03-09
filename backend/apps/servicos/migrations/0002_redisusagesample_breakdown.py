# Add breakdown fields to RedisUsageSample (keys_profile_pic, keys_webhook)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("servicos", "0001_redisusagesample"),
    ]

    operations = [
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
    ]
