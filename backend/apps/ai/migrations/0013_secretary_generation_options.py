# Secretária: parâmetros de geração da IA (temperature, top_p, etc.) - override por tenant

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0012_add_message_embedding_cache'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenantsecretaryprofile',
            name='generation_options_override',
            field=models.JSONField(
                blank=True,
                default=None,
                help_text='Override de parâmetros de geração (temperature, top_p, top_k, repeat_penalty, min_p, num_ctx). Null = usar defaults.',
                null=True,
            ),
        ),
    ]
