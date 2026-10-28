"""Receita da categoria — capabilities + libraries (Fase 2).

UI conversacional; aqui só persiste o modelo normalizado.
Não rematerializa produtos existentes (prompt de aplicação = Fase 3).
"""

from django.db import transaction

from apps.catalog.domain.enums import PRODUCT_PRICE_KINDS, CatalogKind
from apps.catalog.models import (
    Category,
    CategoryCapability,
    CategoryLibrary,
    CategoryLibraryItem,
    CategoryOptionPrice,
    Option,
    OptionGroup,
)
from apps.catalog.services.catalog_cache import invalidate_catalog_cache
from apps.catalog.services.category_option_price_service import CategoryOptionPriceService


class CategoryRecipeError(Exception):
    def __init__(self, message: str, code: str = "invalid_recipe"):
        self.message = message
        self.code = code
        super().__init__(message)


class CategoryRecipeService:
    VALID_KINDS = {choice.value for choice in CatalogKind}

    @staticmethod
    def get(category: Category) -> dict:
        caps = (
            CategoryCapability.all_objects.filter(category=category)
            .order_by("sort_order", "kind")
        )
        libraries = (
            CategoryLibrary.all_objects.filter(category=category)
            .select_related("option_group")
            .order_by("sort_order")
        )

        library_payload = []
        for lib in libraries:
            items = (
                CategoryLibraryItem.all_objects.filter(category_library=lib)
                .select_related("option")
                .order_by("sort_order")
            )
            library_payload.append(
                {
                    "kind": lib.kind,
                    "option_group_id": str(lib.option_group_id),
                    "option_group_name": lib.option_group.name,
                    "sort_order": lib.sort_order,
                    "option_ids": [str(item.option_id) for item in items],
                    "options": [
                        {
                            "id": str(item.option_id),
                            "name": item.option.name,
                            "settings": item.settings or {},
                        }
                        for item in items
                    ],
                    "item_settings": {
                        str(item.option_id): item.settings or {}
                        for item in items
                        if item.settings
                    },
                }
            )

        option_prices = [
            {
                "option_id": str(row.option_id),
                "price": float(row.price),
            }
            for row in CategoryOptionPrice.all_objects.filter(category=category).order_by(
                "option_id"
            )
        ]

        return {
            "category_id": str(category.id),
            "category_name": category.name,
            "template_key": category.template_key or "",
            "capabilities": [
                {
                    "kind": cap.kind,
                    "enabled": cap.enabled,
                    "is_required": cap.is_required,
                    "sort_order": cap.sort_order,
                    "settings": cap.settings or {},
                }
                for cap in caps
            ],
            "libraries": library_payload,
            "option_prices": option_prices,
        }

    @staticmethod
    @transaction.atomic
    def replace(category: Category, *, data: dict) -> dict:
        """Troca a receita inteira (após resumo no assistente).

        apply_mode: new_only (padrão) | all | later
        — all rematerializa produtos (cria vínculos; poda preço/vínculo fora da receita).
        — later = igual new_only (salva receita; sem fila de pendência).
        """
        capabilities = data.get("capabilities") or []
        libraries = data.get("libraries") or []
        option_prices = data.get("option_prices") or []
        template_key = data.get("template_key")
        apply_mode = data.get("apply_mode") or "new_only"

        CategoryRecipeService._validate(category, capabilities, libraries)

        # replace completo
        CategoryLibraryItem.all_objects.filter(
            category_library__category=category
        ).delete()
        CategoryLibrary.all_objects.filter(category=category).delete()
        CategoryCapability.all_objects.filter(category=category).delete()

        for index, raw in enumerate(capabilities):
            kind = raw["kind"]
            CategoryCapability.all_objects.create(
                tenant_id=category.tenant_id,
                category=category,
                kind=kind,
                enabled=bool(raw.get("enabled", True)),
                is_required=bool(raw.get("is_required", False)),
                sort_order=int(raw.get("sort_order", index)),
                settings=raw.get("settings") or {},
            )

        for index, raw in enumerate(libraries):
            group_id = raw["option_group_id"]
            kind = raw["kind"]
            lib = CategoryLibrary.all_objects.create(
                tenant_id=category.tenant_id,
                category=category,
                option_group_id=group_id,
                kind=kind,
                sort_order=int(raw.get("sort_order", index)),
            )
            OptionGroup.all_objects.filter(id=group_id, kind="").update(kind=kind)
            # tamanho/volume: preço absoluto (não “+ em cima da base”)
            if kind in PRODUCT_PRICE_KINDS:
                OptionGroup.all_objects.filter(id=group_id).update(
                    pricing_config={"strategy": "replace_base"}
                )

            item_settings = raw.get("item_settings") or {}
            for opt_index, option_id in enumerate(raw.get("option_ids") or []):
                oid = str(option_id)
                raw_settings = item_settings.get(oid) or item_settings.get(option_id) or {}
                settings = CategoryRecipeService._normalize_item_settings(
                    kind=kind,
                    settings=raw_settings if isinstance(raw_settings, dict) else {},
                )
                CategoryLibraryItem.all_objects.create(
                    tenant_id=category.tenant_id,
                    category_library=lib,
                    option_id=option_id,
                    sort_order=opt_index,
                    settings=settings,
                )

        if template_key is not None:
            category.template_key = str(template_key)[:40]
            category.save(update_fields=["template_key", "updated_at"])

        # preços Tipo 2 da categoria (bordas, adicionais…)
        CategoryOptionPriceService.sync(category, option_prices, replace=True)

        apply_result = None
        if apply_mode == "all":
            from apps.catalog.services.materialize_service import MaterializeService

            apply_result = MaterializeService.rematerialize_category(category)

        invalidate_catalog_cache(category.tenant_id)
        recipe = CategoryRecipeService.get(category)
        recipe["apply_mode"] = apply_mode
        if apply_result is not None:
            recipe["apply_result"] = apply_result
        return recipe

    @staticmethod
    def _validate(category: Category, capabilities: list, libraries: list) -> None:
        seen_kinds: set[str] = set()
        for raw in capabilities:
            kind = raw.get("kind")
            if kind not in CategoryRecipeService.VALID_KINDS:
                raise CategoryRecipeError(f"Tipo inválido: {kind}")
            if kind in seen_kinds:
                raise CategoryRecipeError(f"Tipo duplicado na receita: {kind}")
            seen_kinds.add(kind)

        seen_groups: set[str] = set()
        for raw in libraries:
            kind = raw.get("kind")
            if kind not in CategoryRecipeService.VALID_KINDS:
                raise CategoryRecipeError(f"Tipo inválido na biblioteca: {kind}")
            if kind == CatalogKind.HALF:
                raise CategoryRecipeError("Meio a meio não usa itens da base")

            group_id = str(raw.get("option_group_id") or "")
            if not group_id:
                raise CategoryRecipeError("Falta o conjunto da base do cardápio")
            if group_id in seen_groups:
                raise CategoryRecipeError("Conjunto repetido na receita")
            seen_groups.add(group_id)

            group = OptionGroup.all_objects.filter(
                id=group_id,
                tenant_id=category.tenant_id,
            ).first()
            if not group:
                raise CategoryRecipeError("Conjunto não encontrado na base do cardápio")

            option_ids = [str(oid) for oid in (raw.get("option_ids") or [])]
            if not option_ids:
                raise CategoryRecipeError(
                    f"Selecione pelo menos um item em “{group.name}”"
                )

            valid = set(
                str(oid)
                for oid in Option.all_objects.filter(
                    option_group_id=group_id,
                    tenant_id=category.tenant_id,
                    id__in=option_ids,
                ).values_list("id", flat=True)
            )
            missing = [oid for oid in option_ids if oid not in valid]
            if missing:
                raise CategoryRecipeError("Item não pertence a este conjunto da base")

            item_settings = raw.get("item_settings") or {}
            if item_settings and not isinstance(item_settings, dict):
                raise CategoryRecipeError("Configuração dos tamanhos inválida")
            for oid, settings in item_settings.items():
                if str(oid) not in valid:
                    raise CategoryRecipeError("Configuração aponta tamanho fora da receita")
                if settings is not None and not isinstance(settings, dict):
                    raise CategoryRecipeError("Configuração dos tamanhos inválida")
                CategoryRecipeService._normalize_item_settings(
                    kind=kind,
                    settings=settings or {},
                )

    @staticmethod
    def _normalize_item_settings(*, kind: str, settings: dict) -> dict:
        if not settings:
            return {}
        out: dict = {}
        # só tamanho/volume usam máximo de sabores por opção
        if kind in {CatalogKind.SIZE, CatalogKind.VOLUME} and "max_flavors" in settings:
            try:
                max_flavors = int(settings["max_flavors"])
            except (TypeError, ValueError):
                raise CategoryRecipeError("Máximo de sabores inválido") from None
            if max_flavors < 1 or max_flavors > 4:
                raise CategoryRecipeError("Máximo de sabores vai de 1 a 4")
            out["max_flavors"] = max_flavors
        return out

    @staticmethod
    def size_max_flavors_map(category: Category) -> dict[str, int]:
        """option_id → máximo de sabores, a partir dos tamanhos da receita."""
        libs = CategoryLibrary.all_objects.filter(
            category=category,
            kind=CatalogKind.SIZE,
        )
        out: dict[str, int] = {}
        for lib in libs:
            for item in CategoryLibraryItem.all_objects.filter(category_library=lib):
                raw = (item.settings or {}).get("max_flavors")
                if raw is None:
                    continue
                try:
                    value = int(raw)
                except (TypeError, ValueError):
                    continue
                if 1 <= value <= 4:
                    out[str(item.option_id)] = value
        return out
