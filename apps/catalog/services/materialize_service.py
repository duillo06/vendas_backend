"""Materializa a receita da categoria no runtime (ProductOptionGroup).

Fase 3: chamado no create do produto e no “atualizar todos” da receita.
UI conversacional — aqui só o vínculo técnico.
"""

from django.db import transaction

from apps.catalog.models import (
    Category,
    CategoryLibrary,
    CategoryLibraryItem,
    Option,
    Product,
    ProductComposition,
    ProductOptionExclusion,
    ProductOptionGroup,
    ProductOptionPrice,
)


class MaterializeService:
    @staticmethod
    @transaction.atomic
    def sync_product_from_category(
        product: Product,
        *,
        apply_composition: bool = True,
        prune: bool = False,
    ) -> dict:
        """Garante ProductOptionGroup a partir das libraries da categoria.

        prune=True (apply_mode=all): tira vínculo fora da receita e preço de
        opção que a categoria não oferece mais. Exclusões e preços dos itens
        que continuam na receita ficam.
        """
        category = product.category
        libraries = list(
            CategoryLibrary.all_objects.filter(category=category)
            .select_related("option_group")
            .order_by("sort_order")
        )
        recipe_group_ids = {str(library.option_group_id) for library in libraries}

        created_links = 0
        removed_links = 0
        pruned_prices = 0
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

        if prune:
            for group_id, link in list(existing.items()):
                if group_id in recipe_group_ids:
                    continue
                # grupo saiu da receita — some vínculo e preços daquele grupo
                pruned_prices += MaterializeService._delete_prices_for_group(
                    product, group_id
                )
                link.delete()
                removed_links += 1

            pruned_prices += MaterializeService._prune_prices_outside_recipe(
                product, libraries
            )

        composition_touched = False
        if apply_composition:
            composition_touched = MaterializeService._sync_half_capability(product)

        return {
            "created_links": created_links,
            "removed_links": removed_links,
            "pruned_prices": pruned_prices,
            "libraries": len(libraries),
            "composition_touched": composition_touched,
        }

    @staticmethod
    def rematerialize_category(category: Category) -> dict:
        """Atualiza todos os produtos: cria vínculos novos e poda o que saiu da receita."""
        products = Product.all_objects.filter(
            category=category,
            deleted_at__isnull=True,
        )
        touched = 0
        links = 0
        removed = 0
        pruned = 0
        for product in products:
            result = MaterializeService.sync_product_from_category(product, prune=True)
            touched += 1
            links += result["created_links"]
            removed += result["removed_links"]
            pruned += result["pruned_prices"]
        return {
            "products": touched,
            "created_links": links,
            "removed_links": removed,
            "pruned_prices": pruned,
        }

    @staticmethod
    def _delete_prices_for_group(product: Product, option_group_id: str) -> int:
        option_ids = Option.all_objects.filter(
            option_group_id=option_group_id,
        ).values_list("id", flat=True)
        deleted, _ = ProductOptionPrice.all_objects.filter(
            product=product,
            option_id__in=option_ids,
        ).delete()
        return deleted

    @staticmethod
    def _prune_prices_outside_recipe(product: Product, libraries: list) -> int:
        """Apaga ProductOptionPrice de opção que não está mais na library da categoria."""
        deleted_total = 0
        for library in libraries:
            offered = {
                str(oid)
                for oid in CategoryLibraryItem.all_objects.filter(
                    category_library=library
                ).values_list("option_id", flat=True)
            }
            group_option_ids = {
                str(oid)
                for oid in Option.all_objects.filter(
                    option_group_id=library.option_group_id,
                ).values_list("id", flat=True)
            }
            orphans = group_option_ids - offered
            if not orphans:
                continue
            deleted, _ = ProductOptionPrice.all_objects.filter(
                product=product,
                option_id__in=orphans,
            ).delete()
            deleted_total += deleted
        return deleted_total

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
                "min_parts": int(settings.get("min_parts", 1)),
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
        """None = todas as opções do grupo; set = filtrar (receita − exclusões + preços).

        Se a categoria tem receita e este grupo não está nela, devolve set vazio —
        vínculo órfão não pode liberar a biblioteca inteira no cardápio.
        """
        library = (
            CategoryLibrary.all_objects.filter(
                category_id=product.category_id,
                option_group_id=option_group_id,
            )
            .first()
        )
        if not library:
            # receita existe, mas este grupo saiu — não mostra nada deste grupo
            has_recipe = CategoryLibrary.all_objects.filter(
                category_id=product.category_id,
            ).exists()
            if has_recipe:
                return set()
            return None

        items = list(
            CategoryLibraryItem.all_objects.filter(category_library=library).values_list(
                "option_id", flat=True
            )
        )
        if not items:
            return set()

        allowed = {str(oid) for oid in items}
        # preço neste produto = também oferece, mesmo se a receita da categoria não listou
        group_option_ids = Option.all_objects.filter(
            option_group_id=option_group_id,
            is_active=True,
        ).values_list("id", flat=True)
        priced = ProductOptionPrice.all_objects.filter(
            product=product,
            option_id__in=group_option_ids,
        ).values_list("option_id", flat=True)
        allowed |= {str(oid) for oid in priced}

        excluded = set(
            str(eid)
            for eid in ProductOptionExclusion.all_objects.filter(product=product).values_list(
                "option_id", flat=True
            )
        )
        return allowed - excluded
