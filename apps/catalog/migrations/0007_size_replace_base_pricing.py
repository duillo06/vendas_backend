# Generated manually for size absolute pricing

from django.db import migrations


def set_replace_base_for_sizes(apps, schema_editor):
    OptionGroup = apps.get_model("catalog", "OptionGroup")
    for group in OptionGroup.objects.filter(kind__in=["size", "volume"]):
        config = dict(group.pricing_config or {})
        config["strategy"] = "replace_base"
        group.pricing_config = config
        group.save(update_fields=["pricing_config"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0006_category_option_prices_phase5"),
    ]

    operations = [
        migrations.RunPython(set_replace_base_for_sizes, noop_reverse),
    ]
