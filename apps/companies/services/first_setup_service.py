"""Assistente de 1ª configuração — presets por segmento (sem IA de verdade)."""

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Category, Option, OptionGroup
from apps.catalog.services.catalog_cache import invalidate_catalog_cache
from apps.catalog.services.category_recipe_service import CategoryRecipeService
from apps.catalog.services.product_service import CategoryService
from apps.companies.models import Company
from apps.companies.services.settings_service import SettingsService

DEFAULT_SETUP = {
    "status": "pending",  # pending | completed | dismissed
    "segment": None,
    "steps": [],
    "completed_at": None,
    "dismissed_at": None,
}

# presets determinísticos — linguagem do comerciante, não “features”
SEGMENTS = {
    "pizza": {
        "label": "Pizzaria",
        "emoji": "🍕",
        "tagline": "Tamanhos, bordas e meio a meio.",
        "categories": [
            {
                "name": "Pizzas",
                "emoji": "🍕",
                "template_key": "pizza",
                "groups": [
                    {
                        "kind": "size",
                        "name": "Tamanho",
                        "required": True,
                        "selection_type": "single",
                        "options": ["Broto", "Média", "Grande", "Família"],
                    },
                    {
                        "kind": "crust",
                        "name": "Borda",
                        "required": False,
                        "selection_type": "single",
                        "options": ["Sem borda", "Catupiry", "Cheddar", "Chocolate"],
                    },
                    {
                        "kind": "extras",
                        "name": "Adicionais",
                        "required": False,
                        "selection_type": "multiple",
                        "max_selections": 5,
                        "options": ["Bacon", "Calabresa", "Milho", "Azeitona", "Cebola"],
                    },
                ],
                "half": {"max_parts": 2, "pricing_rule": "highest"},
            },
            {
                "name": "Bebidas",
                "emoji": "🥤",
                "template_key": "drinks",
                "groups": [
                    {
                        "kind": "volume",
                        "name": "Volume",
                        "required": True,
                        "selection_type": "single",
                        "options": ["350 ml", "600 ml", "1 L", "2 L"],
                    },
                ],
                "half": None,
            },
        ],
    },
    "burger": {
        "label": "Lanchonete",
        "emoji": "🍔",
        "tagline": "Adicionais, molhos e montagem.",
        "categories": [
            {
                "name": "Lanches",
                "emoji": "🍔",
                "template_key": "burger",
                "groups": [
                    {
                        "kind": "extras",
                        "name": "Adicionais",
                        "required": False,
                        "selection_type": "multiple",
                        "max_selections": 6,
                        "options": ["Bacon", "Queijo", "Ovo", "Calabresa", "Catupiry"],
                    },
                    {
                        "kind": "sauces",
                        "name": "Molhos",
                        "required": False,
                        "selection_type": "multiple",
                        "max_selections": 3,
                        "options": ["Ketchup", "Maionese", "Mostarda", "Barbecue"],
                    },
                ],
                "half": None,
            },
            {
                "name": "Bebidas",
                "emoji": "🥤",
                "template_key": "drinks",
                "groups": [
                    {
                        "kind": "volume",
                        "name": "Volume",
                        "required": True,
                        "selection_type": "single",
                        "options": ["Lata", "600 ml", "1 L"],
                    },
                ],
                "half": None,
            },
        ],
    },
    "acai": {
        "label": "Açaí / Sorveteria",
        "emoji": "🫐",
        "tagline": "Tamanhos e complementos.",
        "categories": [
            {
                "name": "Açaí",
                "emoji": "🫐",
                "template_key": "acai",
                "groups": [
                    {
                        "kind": "size",
                        "name": "Tamanho",
                        "required": True,
                        "selection_type": "single",
                        "options": ["300 ml", "500 ml", "700 ml", "1 L"],
                    },
                    {
                        "kind": "extras",
                        "name": "Complementos",
                        "required": False,
                        "selection_type": "multiple",
                        "max_selections": 8,
                        "options": ["Granola", "Banana", "Morango", "Leite condensado", "Paçoca"],
                    },
                ],
                "half": None,
            },
        ],
    },
    "pastel": {
        "label": "Pastelaria",
        "emoji": "🥟",
        "tagline": "Recheios e tamanhos.",
        "categories": [
            {
                "name": "Pastéis",
                "emoji": "🥟",
                "template_key": "pastel",
                "groups": [
                    {
                        "kind": "size",
                        "name": "Tamanho",
                        "required": True,
                        "selection_type": "single",
                        "options": ["Pequeno", "Grande"],
                    },
                    {
                        "kind": "buildable",
                        "name": "Recheios",
                        "required": True,
                        "selection_type": "multiple",
                        "max_selections": 4,
                        "options": ["Queijo", "Carne", "Frango", "Calabresa", "Palmito"],
                    },
                ],
                "half": None,
            },
        ],
    },
    "other": {
        "label": "Outro / Vários",
        "emoji": "✨",
        "tagline": "Começamos com categorias simples — você ajusta depois.",
        "categories": [
            {
                "name": "Cardápio",
                "emoji": "🍽️",
                "template_key": "generic",
                "groups": [
                    {
                        "kind": "extras",
                        "name": "Adicionais",
                        "required": False,
                        "selection_type": "multiple",
                        "max_selections": 5,
                        "options": ["Extra 1", "Extra 2"],
                    },
                ],
                "half": None,
            },
        ],
    },
}


class FirstSetupError(Exception):
    def __init__(self, message: str, code: str = "setup_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class FirstSetupService:
    @staticmethod
    def normalize(setup: dict | None) -> dict:
        base = dict(DEFAULT_SETUP)
        if isinstance(setup, dict):
            base.update({k: v for k, v in setup.items() if k in base or k in setup})
        if not base.get("status"):
            base["status"] = "pending"
        if base.get("steps") is None:
            base["steps"] = []
        return base

    @staticmethod
    def get(company: Company) -> dict:
        settings = SettingsService.get_for_tenant(company)
        return FirstSetupService.normalize(settings.setup)

    @staticmethod
    def list_segments() -> list[dict]:
        return [
            {
                "id": key,
                "label": meta["label"],
                "emoji": meta["emoji"],
                "tagline": meta["tagline"],
            }
            for key, meta in SEGMENTS.items()
        ]

    @staticmethod
    def save_setup(company: Company, patch: dict) -> dict:
        settings = SettingsService.get_for_tenant(company)
        current = FirstSetupService.normalize(settings.setup)
        for key in ("status", "segment", "steps", "completed_at", "dismissed_at"):
            if key in patch:
                current[key] = patch[key]
        settings.setup = current
        settings.save(update_fields=["setup", "updated_at"])
        return current

    @staticmethod
    def dismiss(company: Company) -> dict:
        return FirstSetupService.save_setup(
            company,
            {
                "status": "dismissed",
                "dismissed_at": timezone.now().isoformat(),
            },
        )

    @staticmethod
    def complete(company: Company, *, segment: str | None = None) -> dict:
        patch = {
            "status": "completed",
            "completed_at": timezone.now().isoformat(),
        }
        if segment:
            patch["segment"] = segment
        return FirstSetupService.save_setup(company, patch)

    @staticmethod
    @transaction.atomic
    def apply_segment(company: Company, segment: str) -> dict:
        if segment not in SEGMENTS:
            raise FirstSetupError("Segmento inválido")

        preset = SEGMENTS[segment]
        created_categories = []

        for index, cat_spec in enumerate(preset["categories"]):
            category = FirstSetupService._ensure_category(
                company,
                name=cat_spec["name"],
                emoji=cat_spec.get("emoji") or "",
                template_key=cat_spec.get("template_key") or "",
                sort_order=index,
            )
            capabilities = []
            libraries = []
            sort_cap = 0

            for g_index, group_spec in enumerate(cat_spec.get("groups") or []):
                group, option_ids = FirstSetupService._ensure_group_with_options(
                    company,
                    group_spec,
                )
                kind = group_spec["kind"]
                capabilities.append(
                    {
                        "kind": kind,
                        "enabled": True,
                        "is_required": bool(group_spec.get("required")),
                        "sort_order": sort_cap,
                        "settings": {},
                    }
                )
                sort_cap += 1
                libraries.append(
                    {
                        "kind": kind,
                        "option_group_id": str(group.id),
                        "sort_order": g_index,
                        "option_ids": option_ids,
                    }
                )

            half = cat_spec.get("half")
            if half:
                capabilities.append(
                    {
                        "kind": "half",
                        "enabled": True,
                        "is_required": False,
                        "sort_order": sort_cap,
                        "settings": {
                            "min_parts": 1,
                            "max_parts": int(half.get("max_parts", 2)),
                            "pricing_rule": half.get("pricing_rule", "highest"),
                            "label": "Escolher outro sabor",
                        },
                    }
                )

            if capabilities:
                CategoryRecipeService.replace(
                    category,
                    data={
                        "capabilities": capabilities,
                        "libraries": libraries,
                        "template_key": cat_spec.get("template_key") or "",
                        "apply_mode": "new_only",
                    },
                )

            created_categories.append(
                {
                    "id": str(category.id),
                    "name": category.name,
                    "emoji": category.emoji,
                }
            )

        setup = FirstSetupService.save_setup(
            company,
            {
                "status": "completed",
                "segment": segment,
                "steps": ["segment", "preset_applied"],
                "completed_at": timezone.now().isoformat(),
            },
        )
        invalidate_catalog_cache(company.id)
        return {
            "setup": setup,
            "segment": segment,
            "categories": created_categories,
        }

    @staticmethod
    def _ensure_category(company, *, name, emoji, template_key, sort_order):
        existing = Category.all_objects.filter(
            tenant=company,
            name__iexact=name,
            deleted_at__isnull=True,
        ).first()
        if existing:
            if template_key and not existing.template_key:
                existing.template_key = template_key
                existing.save(update_fields=["template_key", "updated_at"])
            return existing
        return CategoryService.create(
            tenant=company,
            data={
                "name": name,
                "emoji": emoji,
                "is_active": True,
                "sort_order": sort_order,
                "template_key": template_key,
            },
        )

    @staticmethod
    def _ensure_group_with_options(company, group_spec: dict):
        kind = group_spec["kind"]
        name = group_spec["name"]
        group = OptionGroup.all_objects.filter(
            tenant=company,
            name__iexact=name,
        ).first()
        if not group:
            group = OptionGroup.all_objects.create(
                tenant=company,
                name=name,
                description="",
                selection_type=group_spec.get("selection_type", "single"),
                min_selections=1 if group_spec.get("required") else 0,
                max_selections=(
                    1
                    if group_spec.get("selection_type", "single") == "single"
                    else int(group_spec.get("max_selections") or 5)
                ),
                is_required=bool(group_spec.get("required")),
                kind=kind,
                pricing_config={"strategy": "additive"},
            )
        elif not group.kind:
            group.kind = kind
            group.save(update_fields=["kind", "updated_at"])

        option_ids = []
        for opt_index, opt_name in enumerate(group_spec.get("options") or []):
            option = Option.all_objects.filter(
                tenant=company,
                option_group=group,
                name__iexact=opt_name,
            ).first()
            if not option:
                option = Option.all_objects.create(
                    tenant=company,
                    option_group=group,
                    name=opt_name,
                    price_modifier=0,
                    sort_order=opt_index,
                    is_active=True,
                    is_available=True,
                )
            option_ids.append(str(option.id))
        return group, option_ids
