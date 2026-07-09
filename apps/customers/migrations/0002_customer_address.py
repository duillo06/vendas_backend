# Generated manually for Sprint 11

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0001_initial"),
        ("customers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerAddress",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("label", models.CharField(blank=True, default="", max_length=50)),
                ("street", models.CharField(max_length=255)),
                ("number", models.CharField(max_length=20)),
                ("complement", models.CharField(blank=True, default="", max_length=100)),
                ("neighborhood", models.CharField(max_length=100)),
                ("city", models.CharField(max_length=100)),
                ("state", models.CharField(max_length=2)),
                ("zip_code", models.CharField(max_length=9)),
                ("reference", models.CharField(blank=True, default="", max_length=255)),
                ("latitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("is_default", models.BooleanField(default=False)),
                (
                    "customer",
                    models.ForeignKey(
                        db_column="customer_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="addresses",
                        to="customers.customer",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(class)ss",
                        to="companies.company",
                    ),
                ),
            ],
            options={
                "db_table": "customer_addresses",
                "ordering": ["-is_default", "-created_at"],
                "indexes": [
                    models.Index(fields=["customer"], name="customer_ad_custome_0f0f0d_idx"),
                    models.Index(fields=["tenant", "customer"], name="customer_ad_tenant__a1b2c3_idx"),
                ],
            },
        ),
    ]
