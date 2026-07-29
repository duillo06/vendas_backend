from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("locations", "0001_initial"),
        ("customers", "0003_customeraddress_zip_optional"),
    ]

    operations = [
        migrations.AddField(
            model_name="customeraddress",
            name="city_ref",
            field=models.ForeignKey(
                blank=True,
                db_column="city_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="customer_addresses",
                to="locations.city",
            ),
        ),
    ]
