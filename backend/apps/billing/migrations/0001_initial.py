# Generated migration for Plan model

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenancy', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Plan',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('price', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('billing_cycle_days', models.IntegerField(default=30, help_text='Billing cycle in days')),
                ('is_free', models.BooleanField(default=False, help_text='Free plan (no billing)')),
                ('max_connections', models.IntegerField(default=1, help_text='-1 for unlimited')),
                ('max_messages_per_month', models.IntegerField(default=1000, help_text='-1 for unlimited')),
                ('features', models.JSONField(default=list, help_text='List of features')),
                ('is_active', models.BooleanField(default=True)),
                ('stripe_price_id', models.CharField(blank=True, help_text='Stripe Price ID', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Plan',
                'verbose_name_plural': 'Plans',
                'db_table': 'billing_plan',
                'ordering': ['price'],
            },
        ),
    ]
