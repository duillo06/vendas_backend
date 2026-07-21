"""Copia price_modifier legado → product_option_prices (dual-write safe)."""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Option, ProductOptionGroup, ProductOptionPrice


class Command(BaseCommand):
    help = "Backfill: grava preço de cada opção no produto (Fase 0 dual-read)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Só mostra o que faria",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry = options["dry_run"]
        created = 0
        skipped = 0

        links = ProductOptionGroup.objects.select_related("product", "option_group").all()
        for link in links:
            options = Option.objects.filter(option_group_id=link.option_group_id, is_active=True)
            for option in options:
                exists = ProductOptionPrice.all_objects.filter(
                    product_id=link.product_id,
                    option_id=option.id,
                ).exists()
                if exists:
                    skipped += 1
                    continue
                if dry:
                    created += 1
                    continue
                ProductOptionPrice.all_objects.create(
                    tenant_id=link.product.tenant_id,
                    product_id=link.product_id,
                    option_id=option.id,
                    price=Decimal(option.price_modifier or 0),
                )
                created += 1

        mode = "dry-run" if dry else "ok"
        self.stdout.write(
            self.style.SUCCESS(f"[{mode}] product_option_prices: +{created}, skip={skipped}")
        )
