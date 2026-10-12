# Generated migration to remove Notification model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_notification"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Notification",
        ),
    ]