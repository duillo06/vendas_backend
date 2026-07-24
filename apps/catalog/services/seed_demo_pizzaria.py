"""Seed 100% pizzaria — pizzas + bebidas, com fotos, tamanhos e bordas."""

from __future__ import annotations

import logging
import os
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.catalog.domain.enums import CatalogKind, OptionSelectionType
from apps.catalog.models import Category, Option, OptionGroup, Product, ProductImage
from apps.catalog.selectors.catalog_selector import ProductImageService
from apps.catalog.services.catalog_cache import invalidate_catalog_cache
from apps.catalog.services.category_option_price_service import CategoryOptionPriceService
from apps.catalog.services.option_group_service import OptionGroupService
from apps.catalog.services.product_option_price_service import ProductOptionPriceService
from apps.catalog.services.product_service import ProductService
from apps.companies.models import Company
from apps.companies.services.logo_service import CompanyLogoService
from apps.companies.services.settings_service import SettingsService
from apps.promotions.models import Campaign
from apps.promotions.services.campaign_service import CampaignService
from core.tenancy.context import TenantContext

logger = logging.getLogger(__name__)

USER_AGENT = "FoodServicePizzariaSeed/1.0 (+local-dev)"

# Unsplash — pizza e bebida (crop estável)
PHOTO = {
    "pizza": [
        "https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1604382354936-07c5d9983bd3?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1593560708920-61dd98c46a4e?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1628840042765-356f4d1e0b5a?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1571997478779-2adcbbe9ab2f?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1588315029754-2dd089d39a1a?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1534308983496-4fabb3a687c0?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1594007654729-407eedc4be12?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1571407970349-0486c308a6b5?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1601924582970-9238bcb495d2?auto=format&fit=crop&w=800&h=600&q=80",
    ],
    "drink": [
        "https://images.unsplash.com/photo-1544145945-f90425340c7e?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1622597467836-f3285f2131b8?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1523677011786-c03c3c7e0fae?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1556679343-c7306c1976bc?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1548839140-29a749e1cf4d?auto=format&fit=crop&w=800&h=600&q=80",
    ],
    "cover": "https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=1400&h=600&q=80",
    "logo": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?auto=format&fit=crop&w=400&h=400&q=80",
}

# name, preço P/M/G, tags, descrição
PIZZAS: list[tuple[str, tuple[str, str, str], list[str], str]] = [
    (
        "Mussarela",
        ("29.90", "39.90", "49.90"),
        ["mais vendido", "favorito"],
        "Molho de tomate e mussarela.",
    ),
    (
        "Margherita",
        ("32.90", "42.90", "54.90"),
        ["mais vendido", "destaque"],
        "Mussarela, tomate e manjericão fresco.",
    ),
    (
        "Calabresa",
        ("34.90", "44.90", "56.90"),
        ["mais vendido", "popular"],
        "Calabresa fatiada e cebola.",
    ),
    (
        "Frango com Catupiry",
        ("36.90", "46.90", "58.90"),
        ["favorito", "destaque"],
        "Frango desfiado e catupiry.",
    ),
    (
        "Portuguesa",
        ("37.90", "47.90", "59.90"),
        ["popular"],
        "Presunto, ovo, cebola, azeitona e ervilha.",
    ),
    (
        "Quatro Queijos",
        ("38.90", "48.90", "62.90"),
        ["favorito"],
        "Mussarela, gorgonzola, parmesão e provolone.",
    ),
    (
        "Bacon",
        ("38.90", "48.90", "61.90"),
        ["destaque"],
        "Bacon crocante e mussarela.",
    ),
    (
        "Pepperoni",
        ("39.90", "49.90", "64.90"),
        ["novidade", "novo"],
        "Pepperoni e orégano.",
    ),
    (
        "Vegetariana",
        ("35.90", "45.90", "57.90"),
        ["novo"],
        "Tomate, pimentão, cebola, azeitona e milho.",
    ),
    (
        "Chocolate",
        ("32.90", "42.90", "52.90"),
        ["novidade"],
        "Pizza doce com chocolate ao leite.",
    ),
    (
        "Romeu e Julieta",
        ("34.90", "44.90", "54.90"),
        [],
        "Goiabada e queijo cremoso.",
    ),
]

BEBIDAS: list[tuple[str, str, list[str], str]] = [
    ("Refrigerante Lata", "6.90", ["mais vendido"], "350ml gelado."),
    ("Refrigerante 2L", "14.90", ["popular", "destaque"], "Garrafa 2 litros."),
    ("Suco Natural", "12.90", ["favorito"], "Laranja ou limão — 500ml."),
    ("Água Mineral", "4.90", [], "500ml sem gás."),
    ("Água com Gás", "5.50", [], "500ml."),
]


def _download(url: str, timeout: int = 25) -> tuple[bytes, str] | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            ctype = (resp.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip().lower()
            if ctype not in {"image/jpeg", "image/png", "image/webp"}:
                if data[:3] == b"\xff\xd8\xff":
                    ctype = "image/jpeg"
                elif data[:8] == b"\x89PNG\r\n\x1a\n":
                    ctype = "image/png"
                else:
                    ctype = "image/jpeg"
            if not data or len(data) < 500:
                return None
            return data, ctype
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("falha ao baixar %s: %s", url, exc)
        return None


def _as_image_file(data: bytes, content_type: str, name: str) -> ContentFile:
    by_type = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    filename = f"{slugify(name) or 'img'}{by_type.get(content_type, '.jpg')}"
    file = ContentFile(data, name=filename)
    file.content_type = content_type
    return file


def _pick_url(photo_key: str, index: int) -> str:
    urls = PHOTO.get(photo_key) or PHOTO["pizza"]
    if isinstance(urls, str):
        return urls
    return urls[index % len(urls)]


def _ensure_category(company: Company, *, name: str, slug: str, emoji: str, description: str, sort_order: int) -> Category:
    existing = Category.all_objects.filter(tenant=company, slug=slug).first()
    if existing:
        existing.name = name
        existing.emoji = emoji
        existing.description = description
        existing.sort_order = sort_order
        existing.is_active = True
        existing.deleted_at = None
        existing.save()
        return existing

    return Category.all_objects.create(
        tenant=company,
        name=name,
        slug=slug,
        emoji=emoji,
        description=description,
        sort_order=sort_order,
        is_active=True,
    )


def _ensure_product(
    company: Company,
    category: Category,
    name: str,
    base_price: str,
    tags: list[str],
    description: str,
    sort_order: int,
    option_group_ids: list,
) -> Product:
    slug = slugify(name)
    existing = Product.all_objects.filter(tenant=company, slug=slug).first()
    if existing:
        existing.category = category
        existing.base_price = Decimal(base_price)
        existing.tags = tags
        existing.description = description
        existing.is_active = True
        existing.is_available = True
        existing.sort_order = sort_order
        existing.deleted_at = None
        existing.save()
        if option_group_ids is not None:
            OptionGroupService.sync_product_groups(existing, option_group_ids)
        return existing

    return ProductService.create(
        tenant=company,
        data={
            "name": name,
            "slug": slug,
            "description": description,
            "base_price": Decimal(base_price),
            "category_id": category.id,
            "is_active": True,
            "is_available": True,
            "tags": tags,
            "sort_order": sort_order,
            "option_group_ids": option_group_ids,
            "from_recipe": False,
        },
    )


def _attach_image(product: Product, url: str, log: Callable[[str], None]) -> bool:
    if ProductImage.all_objects.filter(product=product).exists():
        return False
    downloaded = _download(url)
    if not downloaded:
        log(f"  ⚠ sem foto: {product.name}")
        return False
    data, ctype = downloaded
    try:
        ProductImageService.add_image(
            product=product,
            image_file=_as_image_file(data, ctype, product.slug),
            alt_text=product.name,
            is_primary=True,
        )
        return True
    except Exception as exc:  # noqa: BLE001 — seed local
        log(f"  ⚠ foto {product.name}: {exc}")
        return False


def _set_category_cover(category: Category, url: str, log: Callable[[str], None]) -> None:
    if category.image_url:
        return
    downloaded = _download(url)
    if not downloaded:
        return
    data, ctype = downloaded
    file = _as_image_file(data, ctype, category.slug)
    ext = os.path.splitext(file.name)[1] or ".jpg"
    path = f"{category.tenant_id}/categories/{uuid.uuid4()}{ext}"
    saved = default_storage.save(path, file)
    category.image_url = default_storage.url(saved)
    category.save(update_fields=["image_url", "updated_at"])
    log(f"  capa categoria: {category.name}")


def _branding(company: Company, log: Callable[[str], None], skip_images: bool) -> None:
    if skip_images:
        return
    if not company.logo_url:
        downloaded = _download(PHOTO["logo"])
        if downloaded:
            data, ctype = downloaded
            try:
                CompanyLogoService.upload(
                    company=company,
                    image_file=_as_image_file(data, ctype, "logo"),
                )
                log("logo da pizzaria atualizado")
            except Exception as exc:  # noqa: BLE001
                log(f"logo falhou: {exc}")
    company.refresh_from_db()
    if not company.cover_url:
        downloaded = _download(PHOTO["cover"])
        if downloaded:
            data, ctype = downloaded
            try:
                CompanyLogoService.upload_cover(
                    company=company,
                    image_file=_as_image_file(data, ctype, "cover"),
                )
                log("capa da pizzaria atualizada")
            except Exception as exc:  # noqa: BLE001
                log(f"capa falhou: {exc}")


def _ensure_option_group(
    company: Company,
    *,
    name: str,
    kind: str,
    required: bool,
    pricing_strategy: str,
    options: list[tuple[str, str]],
) -> tuple[OptionGroup, dict[str, Option]]:
    """options: [(nome, preço_modificador_zero), ...] — preços reais vão no produto/categoria."""
    group = OptionGroup.all_objects.filter(tenant=company, name=name, kind=kind).first()
    if group is None:
        group = OptionGroupService.create(
            tenant=company,
            data={
                "name": name,
                "description": "",
                "kind": kind,
                "selection_type": OptionSelectionType.SINGLE,
                "min_selections": 1 if required else 0,
                "max_selections": 1,
                "is_required": required,
                "sort_order": 0 if kind == CatalogKind.SIZE else 1,
                "is_active": True,
                "pricing_config": {"strategy": pricing_strategy},
            },
        )
    else:
        group.is_required = required
        group.min_selections = 1 if required else 0
        group.max_selections = 1
        group.pricing_config = {"strategy": pricing_strategy}
        group.is_active = True
        group.save()

    by_name: dict[str, Option] = {}
    for idx, (opt_name, _mod) in enumerate(options):
        existing = Option.all_objects.filter(option_group=group, name=opt_name).first()
        if existing:
            existing.is_active = True
            existing.is_available = True
            existing.sort_order = idx
            existing.price_modifier = Decimal("0")
            existing.save()
            by_name[opt_name] = existing
        else:
            by_name[opt_name] = OptionGroupService.create_option(
                group=group,
                data={
                    "name": opt_name,
                    "price_modifier": Decimal("0"),
                    "sort_order": idx,
                    "is_active": True,
                    "is_available": True,
                },
            )
    return group, by_name


def _seed_campaigns(company: Company, products_by_slug: dict[str, Product], log: Callable[[str], None]) -> None:
    specs = [
        ("margherita", "36.90", 200, "Margherita em promoção"),
        ("calabresa", "39.90", 150, "Calabresa da casa"),
        ("refrigerante-2l", "11.90", 80, "Refri 2L com desconto"),
    ]
    now = timezone.now()
    created = 0
    for slug, promo, weight, title in specs:
        product = products_by_slug.get(slug)
        if not product:
            continue
        if Campaign.all_objects.filter(tenant=company, product=product, status="active").exists():
            continue
        CampaignService.create(
            tenant=company,
            data={
                "product_id": product.id,
                "promo_price": promo,
                "title": title,
                "weight": weight,
                "show_on_home": True,
                "show_on_menu": True,
                "show_on_product": True,
                "starts_at": now - timedelta(hours=1),
                "ends_at": now + timedelta(days=14),
            },
        )
        created += 1
    log(f"campanhas criadas: {created}")


@transaction.atomic
def seed_demo_pizzaria(
    company: Company,
    *,
    skip_images: bool = False,
    log: Callable[[str], None] | None = None,
) -> dict:
    """Cardápio de pizzaria (idempotente por slug)."""
    log = log or (lambda msg: None)
    stats = {"categories": 0, "products": 0, "images": 0}

    TenantContext.set(company)
    try:
        SettingsService.update(
            company,
            auto_close_outside_hours=False,
            is_open=True,
            delivery_city="São Paulo",
            delivery_state="SP",
        )
        _branding(company, log, skip_images)

        size_group, sizes = _ensure_option_group(
            company,
            name="Tamanho",
            kind=CatalogKind.SIZE,
            required=True,
            pricing_strategy="replace_base",
            options=[
                ("Pequena (4 fatias)", "0"),
                ("Média (6 fatias)", "0"),
                ("Grande (8 fatias)", "0"),
            ],
        )
        crust_group, crusts = _ensure_option_group(
            company,
            name="Borda",
            kind=CatalogKind.CRUST,
            required=False,
            pricing_strategy="additive",
            options=[
                ("Sem borda", "0"),
                ("Catupiry", "0"),
                ("Cheddar", "0"),
                ("Chocolate", "0"),
            ],
        )
        log("grupos: Tamanho + Borda")

        pizzas_cat = _ensure_category(
            company,
            name="Pizzas",
            slug="pizzas",
            emoji="🍕",
            description="Massas artesanais — escolha o tamanho e a borda",
            sort_order=0,
        )
        bebidas_cat = _ensure_category(
            company,
            name="Bebidas",
            slug="bebidas",
            emoji="🥤",
            description="Para acompanhar a pizza",
            sort_order=1,
        )
        stats["categories"] = 2
        log(f"categoria: {pizzas_cat.name}")
        log(f"categoria: {bebidas_cat.name}")

        if not skip_images:
            _set_category_cover(pizzas_cat, _pick_url("pizza", 0), log)
            _set_category_cover(bebidas_cat, _pick_url("drink", 0), log)

        # preços de borda na categoria (herança)
        CategoryOptionPriceService.sync(
            pizzas_cat,
            [
                {"option_id": crusts["Sem borda"].id, "price": "0"},
                {"option_id": crusts["Catupiry"].id, "price": "12.00"},
                {"option_id": crusts["Cheddar"].id, "price": "12.00"},
                {"option_id": crusts["Chocolate"].id, "price": "15.00"},
            ],
            replace=True,
        )

        pizza_group_ids = [size_group.id, crust_group.id]
        products_by_slug: dict[str, Product] = {}

        for idx, (name, prices, tags, description) in enumerate(PIZZAS):
            price_p, price_m, price_g = prices
            product = _ensure_product(
                company,
                pizzas_cat,
                name,
                price_m,  # base = média (fallback se size não vier)
                tags,
                description,
                sort_order=idx,
                option_group_ids=pizza_group_ids,
            )
            ProductOptionPriceService.sync(
                product,
                [
                    {"option_id": sizes["Pequena (4 fatias)"].id, "price": price_p},
                    {"option_id": sizes["Média (6 fatias)"].id, "price": price_m},
                    {"option_id": sizes["Grande (8 fatias)"].id, "price": price_g},
                ],
                replace=True,
            )
            products_by_slug[product.slug] = product
            stats["products"] += 1

            if not skip_images:
                if _attach_image(product, _pick_url("pizza", idx + 1), log):
                    stats["images"] += 1
                    log(f"  ✓ foto: {product.name}")

        for idx, (name, price, tags, description) in enumerate(BEBIDAS):
            product = _ensure_product(
                company,
                bebidas_cat,
                name,
                price,
                tags,
                description,
                sort_order=idx,
                option_group_ids=[],
            )
            products_by_slug[product.slug] = product
            stats["products"] += 1

            if not skip_images:
                if _attach_image(product, _pick_url("drink", idx), log):
                    stats["images"] += 1
                    log(f"  ✓ foto: {product.name}")

        _seed_campaigns(company, products_by_slug, log)
        invalidate_catalog_cache(company.id)
        log(
            f"pronto — {stats['categories']} categorias, "
            f"{stats['products']} produtos, {stats['images']} fotos novas"
        )
        return stats
    finally:
        TenantContext.clear()
