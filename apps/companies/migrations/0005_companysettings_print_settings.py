# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0004_companysettings_delivery_city_ref"),
    ]

    operations = [
        migrations.AddField(
            model_name="companysettings",
            name="print_settings",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
