from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("locations", "0001_initial"),
        ("companies", "0003_companysettings_delivery_city"),
    ]

    operations = [
        migrations.AddField(
            model_name="companysettings",
            name="delivery_city_ref",
            field=models.ForeignKey(
                blank=True,
                db_column="delivery_city_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="company_settings",
                to="locations.city",
            ),
        ),
    ]
