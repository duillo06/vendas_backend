from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="emoji",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
    ]
