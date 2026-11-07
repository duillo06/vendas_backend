import zoneinfo

from django.db import migrations, models
from django.utils import timezone


def backfill_order_business_date(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Company = apps.get_model("companies", "Company")

    timezones = {
        company.id: company.timezone or "America/Sao_Paulo"
        for company in Company.objects.all().only("id", "timezone")
    }
    fallback = zoneinfo.ZoneInfo("America/Sao_Paulo")
    zones = {}

    for order in Order.objects.all().iterator():
        name = timezones.get(order.tenant_id) or "America/Sao_Paulo"
        if name not in zones:
            try:
                zones[name] = zoneinfo.ZoneInfo(name)
            except Exception:
                zones[name] = fallback
        created = order.created_at
        if timezone.is_naive(created):
            created = timezone.make_aware(created, fallback)
        Order.objects.filter(pk=order.pk).update(
            business_date=created.astimezone(zones[name]).date()
        )


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_dining_tables_and_order_table"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="business_date",
            field=models.DateField(null=True),
        ),
        migrations.RunPython(backfill_order_business_date, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="order",
            name="business_date",
            field=models.DateField(default=timezone.localdate),
        ),
        migrations.RemoveConstraint(
            model_name="order",
            name="unique_order_number_per_tenant",
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.UniqueConstraint(
                fields=("tenant", "business_date", "order_number"),
                name="unique_order_number_per_tenant_day",
            ),
        ),
    ]
