from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("promotions", "0001_campaign_fase1"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="weight",
            field=models.PositiveIntegerField(
                default=10,
                help_text="Prioridade na vitrine (maior = mais destaque). Interno.",
            ),
        ),
        migrations.AddIndex(
            model_name="campaign",
            index=models.Index(fields=["tenant", "weight"], name="campaigns_tenant__weight_idx"),
        ),
    ]
