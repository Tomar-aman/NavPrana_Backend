from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_user_is_guest'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='firebase_uid',
            field=models.CharField(
                blank=True,
                error_messages={'unique': 'A user with that Firebase account already exists.'},
                help_text='Firebase account that verified this phone number over SMS.',
                max_length=128,
                null=True,
                unique=True,
                verbose_name='firebase uid',
            ),
        ),
    ]
