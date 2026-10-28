from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0009_product_max_quantity_per_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="categorylibraryitem",
            name="settings",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
