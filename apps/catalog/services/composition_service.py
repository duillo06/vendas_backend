from decimal import Decimal

from django.db.models import QuerySet

from apps.catalog.domain.enums import CompositionPricingRule, CompositionSourceType
from apps.catalog.models import Product, ProductComposition
from core.utils.money import round_money


class CompositionService:
    """Regras da Composição de Produtos (produto formado por outros produtos).

    Genérico: serve pra pizza meio a meio, combos, kits — qualquer caso em que
    um produto é composto por outros já cadastrados.
    """

    @staticmethod
    def get_config(product: Product) -> ProductComposition | None:
        config = getattr(product, "composition", None)
        if config is None or not config.is_enabled:
            return None
        return config

    @staticmethod
    def get_candidates(product: Product) -> QuerySet[Product]:
        """Produtos que podem compor este produto, conforme a fonte configurada."""
        config = CompositionService.get_config(product)
        if config is None:
            return Product.objects.none()

        qs = (
            Product.objects.filter(is_active=True, is_available=True)
            .select_related("category")
            .prefetch_related("images")
            .exclude(id=product.id)
        )

        if config.source_type == CompositionSourceType.TAG and config.source_tag:
            return qs.filter(tags__contains=[config.source_tag]).order_by("sort_order", "name")

        if config.source_type == CompositionSourceType.CUSTOM:
            ids = list(config.custom_products.values_list("id", flat=True))
            return qs.filter(id__in=ids).order_by("sort_order", "name")

        # default: mesma categoria (a do produto, ou a configurada)
        category_id = config.source_category_id or product.category_id
        return qs.filter(category_id=category_id).order_by("sort_order", "name")

    @staticmethod
    def validate_selection(product: Product, component_ids: list) -> list[Product]:
        """Valida os produtos escolhidos pra compor e devolve na ordem recebida."""
        config = CompositionService.get_config(product)
        if config is None:
            if component_ids:
                raise ValueError("Este produto não aceita composição")
            return []

        clean_ids = [str(cid) for cid in component_ids if cid]
        # total de partes = principal + escolhidos
        total_parts = 1 + len(clean_ids)
        if total_parts < config.min_parts or total_parts > config.max_parts:
            raise ValueError(
                f"Escolha entre {config.min_parts - 1} e {config.max_parts - 1} "
                f"produto(s) para compor {product.name}",
            )

        if not clean_ids:
            return []

        candidates = {str(p.id): p for p in CompositionService.get_candidates(product)}
        chosen: list[Product] = []
        for cid in clean_ids:
            match = candidates.get(cid)
            if match is None:
                raise ValueError(f"Produto inválido para compor {product.name}")
            chosen.append(match)
        return chosen

    @staticmethod
    def composed_base_price(product: Product, parts: list[Product]) -> Decimal:
        """Preço base da composição conforme a regra. `parts` inclui o principal."""
        config = CompositionService.get_config(product)
        base = Decimal(product.base_price)
        if config is None or not parts:
            return round_money(base)

        prices = [Decimal(p.base_price) for p in parts]
        if config.pricing_rule == CompositionPricingRule.MAIN:
            return round_money(base)
        if config.pricing_rule == CompositionPricingRule.AVERAGE:
            return round_money(sum(prices) / Decimal(len(prices)))
        if config.pricing_rule == CompositionPricingRule.SUM:
            return round_money(sum(prices))
        # highest (padrão pizza meio a meio: cobra o mais caro)
        return round_money(max(prices))
