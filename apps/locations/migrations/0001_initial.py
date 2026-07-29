from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="State",
            fields=[
                ("id", models.PositiveSmallIntegerField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=50)),
                ("acronym", models.CharField(max_length=2, unique=True)),
            ],
            options={
                "db_table": "states",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="City",
            fields=[
                ("id", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("normalized_name", models.CharField(db_index=True, max_length=100)),
                (
                    "state",
                    models.ForeignKey(
                        db_column="state_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cities",
                        to="locations.state",
                    ),
                ),
            ],
            options={
                "db_table": "cities",
                "ordering": ["name"],
                "indexes": [
                    models.Index(fields=["state", "name"], name="cities_state_name_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("state", "normalized_name"),
                        name="uniq_city_state_normalized_name",
                    ),
                ],
            },
        ),
    ]
