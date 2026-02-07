# Secretária IA: palavras-chave por departamento para roteamento

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authn', '0005_add_transfer_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='department',
            name='routing_keywords',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Lista de palavras-chave para a Secretária IA encaminhar conversas a este departamento (ex: ["financeiro", "boleto", "pagamento"])',
                verbose_name='Palavras-chave para roteamento',
            ),
        ),
    ]
