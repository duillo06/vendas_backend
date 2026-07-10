# Generated manually — Product Builder Engine Fase 2

from django.db import migrations, models


def backfill_display_types(apps, schema_editor):
    OptionGroup = apps.get_model("catalog", "OptionGroup")
    for group in OptionGroup.objects.all():
        if group.selection_type == "multiple":
            group.display_type = "checkbox"
        else:
            group.display_type = "radio"
        group.save(update_fields=["display_type"])


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_category_emoji"),
    ]

    operations = [
        migrations.AddField(
            model_name="optiongroup",
            name="selection_mode",
            field=models.CharField(
                choices=[("pick", "Escolha"), ("quantity", "Quantidade")],
                default="pick",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="optiongroup",
            name="display_type",
            field=models.CharField(
                choices=[
                    ("list", "Lista"),
                    ("radio", "Radio"),
                    ("checkbox", "Checkbox"),
                    ("cards", "Cards"),
                    ("image_cards", "Cards com imagem"),
                    ("dropdown", "Dropdown"),
                    ("stepper", "Stepper"),
                    ("icon_chips", "Chips"),
                    ("color_swatch", "Cor"),
                ],
                default="radio",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="optiongroup",
            name="icon",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
        migrations.AddField(
            model_name="optiongroup",
            name="image_url",
            field=models.URLField(blank=True, null=True, max_length=500),
        ),
        migrations.AddField(
            model_name="optiongroup",
            name="visibility",
            field=models.CharField(
                choices=[("always", "Sempre"), ("hidden", "Oculto")],
                default="always",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="optiongroup",
            name="pricing_config",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="optiongroup",
            name="ui_config",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="optiongroup",
            name="default_option_ids",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="option",
            name="image_url",
            field=models.URLField(blank=True, null=True, max_length=500),
        ),
        migrations.AddField(
            model_name="option",
            name="icon",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
        migrations.AddField(
            model_name="option",
            name="stock_quantity",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="option",
            name="metadata",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="productoptiongroup",
            name="override_required",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="productoptiongroup",
            name="override_display_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("list", "Lista"),
                    ("radio", "Radio"),
                    ("checkbox", "Checkbox"),
                    ("cards", "Cards"),
                    ("image_cards", "Cards com imagem"),
                    ("dropdown", "Dropdown"),
                    ("stepper", "Stepper"),
                    ("icon_chips", "Chips"),
                    ("color_swatch", "Cor"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="productoptiongroup",
            name="override_pricing_config",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="productoptiongroup",
            name="override_ui_config",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_display_types, migrations.RunPython.noop),
    ]
