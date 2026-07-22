from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0002_customer_address"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customeraddress",
            name="zip_code",
            field=models.CharField(blank=True, default="", max_length=9),
        ),
    ]
