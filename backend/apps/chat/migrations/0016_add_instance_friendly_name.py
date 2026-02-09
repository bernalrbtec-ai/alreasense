# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0015_add_transcription_quality_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversation',
            name='instance_friendly_name',
            field=models.CharField(
                blank=True,
                help_text='Nome exibido para o usuário (ex: C_Financeiro)',
                max_length=100,
                verbose_name='Nome Amigável da Instância'
            ),
        ),
    ]
