# Generated manually to add tenant_id to CampaignLog

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('campaigns', '0007_fix_campaign_intervals'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaignlog',
            name='tenant',
            field=models.ForeignKey(
                to='tenancy.tenant',
                on_delete=django.db.models.deletion.CASCADE,
                null=True,
                blank=True,
                related_name='campaign_logs'
            ),
        ),
    ]
