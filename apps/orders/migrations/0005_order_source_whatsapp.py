from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_dining_tables_and_order_table"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="source",
            field=models.CharField(
                choices=[
                    ("storefront", "Storefront"),
                    ("whatsapp", "WhatsApp"),
                    ("backoffice", "Backoffice"),
                    ("api", "API"),
                ],
                default="storefront",
                max_length=20,
            ),
        ),
    ]
