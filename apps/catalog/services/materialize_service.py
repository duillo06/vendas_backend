"""Materializa a receita da categoria no runtime (ProductOptionGroup).

Fase 0: esqueleto seguro — cria vínculos faltantes, não apaga overrides manuais.
UI conversacional entra nas fases seguintes.
"""

from django.db import transaction

from apps.catalog.models import (
    CategoryLibrary,
    Product,
    ProductComposition,
    ProductOptionExclusion,
    ProductOptionGroup,
)


class MaterializeService:
    @staticmethod
    @transaction.atomic
    def sync_product_from_category(product: Product, *, apply_composition: bool = True) -> dict:
        """Garante ProductOptionGroup a partir das libraries da categoria.

        Retorna contagens pra log/admin — sem jargão pro usuário.
        """
        category = product.category
        libraries = (
            CategoryLibrary.objects.filter(category=category)
            .select_related("option_group")
            .order_by("sort_order")
        )

        created_links = 0
        existing = {
            str(link.option_group_id): link
            for link in ProductOptionGroup.objects.filter(product=product)
        }

        for index, library in enumerate(libraries):
            group_id = str(library.option_group_id)
            if group_id in existing:
                link = existing[group_id]
                if link.sort_order != index:
                    link.sort_order = index
                    link.save(update_fields=["sort_order", "updated_at"])
                continue

            ProductOptionGroup.objects.create(
                tenant_id=product.tenant_id,
                product=product,
                option_group_id=library.option_group_id,
                sort_order=index,
            )
            created_links += 1

        composition_touched = False
        if apply_composition:
            composition_touched = MaterializeService._sync_half_capability(product)

        return {
            "created_links": created_links,
            "libraries": libraries.count(),
            "composition_touched": composition_touched,
        }

    @staticmethod
    def _sync_half_capability(product: Product) -> bool:
        """Se a receita tem meio a meio ligado, garante ProductComposition básica."""
        from apps.catalog.domain.enums import CatalogKind
        from apps.catalog.models import CategoryCapability

        cap = CategoryCapability.objects.filter(
            category_id=product.category_id,
            kind=CatalogKind.HALF,
            enabled=True,
        ).first()
        if not cap:
            return False

        settings = cap.settings or {}
        composition, created = ProductComposition.objects.get_or_create(
            product=product,
            defaults={
                "tenant_id": product.tenant_id,
                "is_enabled": True,
                "min_parts": int(settings.get("min_parts", 2)),
                "max_parts": int(settings.get("max_parts", 2)),
                "pricing_rule": settings.get("pricing_rule", "highest"),
                "label": settings.get("label", "Escolher outro sabor"),
            },
        )
        if not created and not composition.is_enabled:
            composition.is_enabled = True
            composition.min_parts = int(settings.get("min_parts", composition.min_parts))
            composition.max_parts = int(settings.get("max_parts", composition.max_parts))
            if settings.get("pricing_rule"):
                composition.pricing_rule = settings["pricing_rule"]
            composition.save()
        return True

    @staticmethod
    def visible_option_ids(product: Product, option_group_id) -> set[str] | None:
        """None = todas as opções do grupo; set = filtrar (receita − exclusões).

        Fase 0: se a categoria tem library items, usa-os; senão None (comportamento legado).
        """
        library = (
            CategoryLibrary.objects.filter(
                category_id=product.category_id,
                option_group_id=option_group_id,
            )
            .prefetch_related("items")
            .first()
        )
        if not library:
            return None

        items = list(library.items.all())
        if not items:
            return None

        allowed = {str(item.option_id) for item in items}
        excluded = set(
            str(eid)
            for eid in ProductOptionExclusion.objects.filter(product=product).values_list(
                "option_id", flat=True
            )
        )
        return allowed - excluded
