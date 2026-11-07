from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_order_business_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="numbering_cycle",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.RemoveConstraint(
            model_name="order",
            name="unique_order_number_per_tenant_day",
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.UniqueConstraint(
                fields=("tenant", "business_date", "numbering_cycle", "order_number"),
                name="unique_order_number_per_tenant_day_cycle",
            ),
        ),
    ]
