from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0006_companysettings_delivery_time_window"),
    ]

    operations = [
        migrations.AddField(
            model_name="companysettings",
            name="order_number_cycle",
            field=models.PositiveIntegerField(default=1),
        ),
    ]
