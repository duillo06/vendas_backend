# Generated manually — sabores opcionais (min_parts = 1)

from django.db import migrations, models


def force_min_parts_one(apps, schema_editor):
    ProductComposition = apps.get_model("catalog", "ProductComposition")
    ProductComposition.objects.filter(min_parts__gt=1).update(min_parts=1)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0007_size_replace_base_pricing"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productcomposition",
            name="min_parts",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.RunPython(force_min_parts_one, noop_reverse),
    ]
