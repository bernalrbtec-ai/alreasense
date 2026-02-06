from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0006_add_gateway_audit'),
    ]

    operations = [
        migrations.AddField(
            model_name='aitranscriptiondailymetric',
            name='quality_correct_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='aitranscriptiondailymetric',
            name='quality_incorrect_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='aitranscriptiondailymetric',
            name='quality_unrated_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='aitranscriptiondailymetric',
            name='avg_latency_ms',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='aitranscriptiondailymetric',
            name='models_used',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
