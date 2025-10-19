# Generated manually to add pending status and make department optional

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0001_initial'),
    ]

    operations = [
        # Adicionar novo status 'pending'
        migrations.AlterField(
            model_name='conversation',
            name='status',
            field=models.CharField(
                choices=[('pending', 'Pendente (Inbox)'), ('open', 'Aberta'), ('closed', 'Fechada')],
                db_index=True,
                default='open',
                max_length=20,
                verbose_name='Status'
            ),
        ),
        # Tornar department nullable
        migrations.AlterField(
            model_name='conversation',
            name='department',
            field=models.ForeignKey(
                blank=True,
                help_text='Null = Conversa pendente no Inbox',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='conversations',
                to='authn.department',
                verbose_name='Departamento'
            ),
        ),
    ]

