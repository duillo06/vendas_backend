from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0005_companysettings_print_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="companysettings",
            name="delivery_time_min",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="companysettings",
            name="delivery_time_max",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
