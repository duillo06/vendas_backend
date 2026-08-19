from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0008_composition_min_parts_optional"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="max_quantity_per_order",
            field=models.PositiveIntegerField(default=10),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.CheckConstraint(
                condition=models.Q(max_quantity_per_order__gte=1)
                & models.Q(max_quantity_per_order__lte=99),
                name="products_max_qty_per_order_range",
            ),
        ),
    ]
