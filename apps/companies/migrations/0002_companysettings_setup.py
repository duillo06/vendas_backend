from django.db import migrations, models


def seed_pending_setup(apps, schema_editor):
    CompanySettings = apps.get_model("companies", "CompanySettings")
    for row in CompanySettings.objects.all():
        if not row.setup:
            row.setup = {"status": "pending", "segment": None, "steps": []}
            row.save(update_fields=["setup"])


class Migration(migrations.Migration):
    dependencies = [
        ("companies", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="companysettings",
            name="setup",
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
        migrations.RunPython(seed_pending_setup, migrations.RunPython.noop),
    ]
