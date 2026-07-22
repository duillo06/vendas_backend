from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("companies", "0002_companysettings_setup"),
    ]

    operations = [
        migrations.AddField(
            model_name="companysettings",
            name="delivery_city",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="companysettings",
            name="delivery_state",
            field=models.CharField(blank=True, default="", max_length=2),
        ),
    ]
