# Cache do texto consolidado em ConsolidationRecord para exibição na UI

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0012_add_message_embedding_cache'),
    ]

    operations = [
        migrations.AddField(
            model_name='consolidationrecord',
            name='content',
            field=models.TextField(blank=True, default=''),
        ),
    ]
