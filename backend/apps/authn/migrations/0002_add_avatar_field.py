# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authn', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='avatar',
            field=models.ImageField(blank=True, help_text='Avatar do usuário', null=True, upload_to='avatars/'),
        ),
    ]
