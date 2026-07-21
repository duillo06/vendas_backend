"""Materializa a receita da categoria no runtime (ProductOptionGroup).

Fase 3: chamado no create do produto e no “atualizar todos” da receita.
UI conversacional — aqui só o vínculo técnico.
"""

from django.db import transaction

from apps.catalog.models import (
    Category,
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

        Não apaga vínculos manuais; não mexe em preços nem exclusões.
        """
        category = product.category
        libraries = list(
            CategoryLibrary.all_objects.filter(category=category)
            .select_related("option_group")
            .order_by("sort_order")
        )

        created_links = 0
        existing = {
            str(link.option_group_id): link
            for link in ProductOptionGroup.all_objects.filter(product=product)
        }

        for index, library in enumerate(libraries):
            group_id = str(library.option_group_id)
            if group_id in existing:
                link = existing[group_id]
                if link.sort_order != index:
                    link.sort_order = index
                    link.save(update_fields=["sort_order", "updated_at"])
                continue

            ProductOptionGroup.all_objects.create(
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
            "libraries": len(libraries),
            "composition_touched": composition_touched,
        }

    @staticmethod
    def rematerialize_category(category: Category) -> dict:
        """Atualiza vínculos de todos os produtos da categoria (preços/exclusões ficam)."""
        products = Product.all_objects.filter(
            category=category,
            deleted_at__isnull=True,
        )
        touched = 0
        links = 0
        for product in products:
            result = MaterializeService.sync_product_from_category(product)
            touched += 1
            links += result["created_links"]
        return {"products": touched, "created_links": links}

    @staticmethod
    def _sync_half_capability(product: Product) -> bool:
        """Se a receita tem meio a meio ligado, garante ProductComposition básica."""
        from apps.catalog.domain.enums import CatalogKind
        from apps.catalog.models import CategoryCapability

        cap = CategoryCapability.all_objects.filter(
            category_id=product.category_id,
            kind=CatalogKind.HALF,
            enabled=True,
        ).first()
        if not cap:
            return False

        settings = cap.settings or {}
        composition, created = ProductComposition.all_objects.get_or_create(
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
        """None = todas as opções do grupo; set = filtrar (receita − exclusões)."""
        library = (
            CategoryLibrary.all_objects.filter(
                category_id=product.category_id,
                option_group_id=option_group_id,
            )
            .first()
        )
        if not library:
            return None

        from apps.catalog.models import CategoryLibraryItem

        items = list(
            CategoryLibraryItem.all_objects.filter(category_library=library).values_list(
                "option_id", flat=True
            )
        )
        if not items:
            return None

        allowed = {str(oid) for oid in items}
        excluded = set(
            str(eid)
            for eid in ProductOptionExclusion.all_objects.filter(product=product).values_list(
                "option_id", flat=True
            )
        )
        return allowed - excluded
