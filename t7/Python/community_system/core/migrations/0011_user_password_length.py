import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0010_alter_abnormalrecord_options_and_more')]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='password',
            field=models.CharField(
                db_column='PASSWORD', max_length=128,
                validators=[django.core.validators.MinLengthValidator(6)],
                verbose_name='密码(6位以上)',
            ),
        ),
    ]
