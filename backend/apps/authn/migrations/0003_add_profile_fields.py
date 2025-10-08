# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authn', '0002_add_avatar_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='display_name',
            field=models.CharField(blank=True, help_text='Nome de exibição', max_length=100),
        ),
        migrations.AddField(
            model_name='user',
            name='phone',
            field=models.CharField(blank=True, help_text='Telefone do usuário', max_length=20),
        ),
        migrations.AddField(
            model_name='user',
            name='birth_date',
            field=models.DateField(blank=True, help_text='Data de nascimento', null=True),
        ),
    ]
