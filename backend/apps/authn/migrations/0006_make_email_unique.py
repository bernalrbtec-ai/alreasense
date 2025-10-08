from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authn', '0005_use_email_as_username'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='email',
            field=models.EmailField(
                unique=True,
                max_length=254,
                help_text='Email address (used for login)'
            ),
        ),
    ]

