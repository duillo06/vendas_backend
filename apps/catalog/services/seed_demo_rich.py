"""Cardápio demo cheio — categorias, produtos com tags da vitrine e fotos baixadas."""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from datetime import timedelta
from decimal import Decimal
from typing import Callable

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.catalog.models import Category, Product, ProductImage
from apps.catalog.selectors.catalog_selector import ProductImageService
from apps.catalog.services.catalog_cache import invalidate_catalog_cache
from apps.catalog.services.product_service import ProductService
from apps.companies.models import Company
from apps.companies.services.logo_service import CompanyLogoService
from apps.companies.services.settings_service import SettingsService
from apps.promotions.services.campaign_service import CampaignService
from core.tenancy.context import TenantContext

logger = logging.getLogger(__name__)

USER_AGENT = "FoodServiceDemoSeed/1.0 (+local-dev)"

# Unsplash CDN — fotos de comida estáveis (crop 800x600)
PHOTO = {
    "burger": [
        "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1550547660-d9450f859349?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1571091718767-18b5b1457add?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1594212699903-ec8a3eca50f5?auto=format&fit=crop&w=800&h=600&q=80",
    ],
    "pizza": [
        "https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1604382354936-07c5d9983bd3?auto=format&fit=crop&w=800&h=600&q=80",
    ],
    "drink": [
        "https://images.unsplash.com/photo-1544145945-f90425340c7e?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1622597467836-f3285f2131b8?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1437418746479-eb914fcfc248?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1556679343-c7306c1976bc?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1523677011786-c03c3c7e0fae?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1497534446932-c925b458314e?auto=format&fit=crop&w=800&h=600&q=80",
    ],
    "dessert": [
        "https://images.unsplash.com/photo-1551024506-0bccd828d307?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1488477181946-6428a0291777?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1563805042-7684c019e1cb?auto=format&fit=crop&w=800&h=600&q=80",
    ],
    "salad": [
        "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1546793665-c74683f339c1?auto=format&fit=crop&w=800&h=600&q=80",
    ],
    "side": [
        "https://images.unsplash.com/photo-1630384060421-cb20d0e0649d?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1541592106381-b31e9677c0e5?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1625944230946-1bb446f98034?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1562967916-eb82221dfb92?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1528735602780-2552fd46c7af?auto=format&fit=crop&w=800&h=600&q=80",
    ],
    "combo": [
        "https://images.unsplash.com/photo-1594212699903-ec8a3eca50f5?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1626082927389-6cd097cdc6ec?auto=format&fit=crop&w=800&h=600&q=80",
    ],
    "coffee": [
        "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&w=800&h=600&q=80",
        "https://images.unsplash.com/photo-1511920170033-f8396924c348?auto=format&fit=crop&w=800&h=600&q=80",
    ],
    "cover": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1400&h=600&q=80",
    "logo": "https://images.unsplash.com/photo-1586190848861-99aa759f1a5e?auto=format&fit=crop&w=400&h=400&q=80",
}

# catálogo: slug estável, emoji, imagem de capa, produtos
CATALOG: list[dict] = [
    {
        "name": "Pizzas",
        "slug": "pizzas",
        "emoji": "🍕",
        "description": "Massas artesanais e sabores clássicos",
        "photo_key": "pizza",
        "products": [
            ("Margherita", "34.90", ["mais vendido", "favorito"], "Molho, mussarela e manjericão."),
            ("Calabresa", "39.90", ["mais vendido", "destaque"], "Calabresa fatiada e cebola."),
            ("Frango com Catupiry", "42.90", ["popular"], "Frango desfiado e catupiry."),
            ("Quatro Queijos", "44.90", ["favorito"], "Mussarela, gorgonzola, parmesão e provolone."),
            ("Pepperoni", "46.90", ["novidade", "novo"], "Pepperoni crocante e orégano."),
            ("Portuguesa", "43.90", [], "Presunto, ovo, cebola e azeitona."),
            ("Vegetariana", "41.90", ["novo"], "Legumes grelhados e mussarela."),
            ("Chocolate", "36.90", ["novidade"], "Pizza doce de sobremesa."),
        ],
    },
    {
        "name": "Lanches",
        "slug": "lanches-premium",
        "emoji": "🍔",
        "description": "Burgers e sanduíches da casa",
        "photo_key": "burger",
        "products": [
            ("Smash Burger", "28.90", ["mais vendido", "destaque"], "Blend smash, queijo e picles."),
            ("X-Bacon", "32.90", ["popular", "favorito"], "Bacon crocante e maionese da casa."),
            ("X-Salada", "26.90", [], "Alface, tomate e queijo."),
            ("Chicken Crispy", "29.90", ["novo"], "Frango empanado e molho especial."),
            ("Veggie Burger", "27.90", ["novidade"], "Hambúrguer de grão-de-bico."),
            ("Duplo Cheddar", "34.90", ["mais vendido"], "Dois blends e cheddar cremoso."),
        ],
    },
    {
        "name": "Combos",
        "slug": "combos",
        "emoji": "👨‍👩‍👧",
        "description": "Prontos pra dividir ou matar a fome",
        "photo_key": "combo",
        "products": [
            ("Combo Família", "89.90", ["combo", "família", "mais vendido"], "2 pizzas médias + 2 refrigerantes."),
            ("Combo Burger", "49.90", ["combo", "kit", "destaque"], "Burger + batata + refri."),
            ("Combo Casal", "69.90", ["combo", "favorito"], "Pizza média + sobremesa + 2 sucos."),
            ("Kit Kids", "32.90", ["kit", "novo"], "Mini burger + batata + suco."),
        ],
    },
    {
        "name": "Bebidas",
        "slug": "bebidas-geladas",
        "emoji": "🥤",
        "description": "Refris, sucos e água",
        "photo_key": "drink",
        "products": [
            ("Refrigerante Lata", "6.90", ["mais vendido"], "350ml."),
            ("Refrigerante 2L", "14.90", ["popular"], "Garrafa 2 litros."),
            ("Suco Natural", "12.90", ["favorito"], "Laranja, limão ou maracujá."),
            ("Água com Gás", "5.50", [], "500ml."),
            ("Milkshake", "18.90", ["novidade", "novo"], "Chocolate, morango ou baunilha."),
            ("Chá Gelado", "9.90", [], "Limão ou pêssego."),
        ],
    },
    {
        "name": "Sobremesas",
        "slug": "sobremesas",
        "emoji": "🍰",
        "description": "Doces pra fechar o pedido",
        "photo_key": "dessert",
        "products": [
            ("Brownie", "14.90", ["mais vendido", "favorito"], "Com calda de chocolate."),
            ("Petit Gateau", "22.90", ["destaque"], "Quente com sorvete."),
            ("Açaí 500ml", "19.90", ["popular", "novo"], "Granola e banana."),
            ("Pudim", "12.90", [], "Fatia generosa."),
            ("Sorvete 2 bolas", "11.90", ["novidade"], "Sabores do dia."),
        ],
    },
    {
        "name": "Porções",
        "slug": "porcoes",
        "emoji": "🍟",
        "description": "Acompanhamentos e petiscos",
        "photo_key": "side",
        "products": [
            ("Batata Frita", "18.90", ["mais vendido"], "Porção individual."),
            ("Batata com Cheddar", "24.90", ["destaque", "favorito"], "Cheddar e bacon."),
            ("Onion Rings", "21.90", ["novo"], "Anéis crocantes."),
            ("Nuggets", "22.90", ["popular"], "10 unidades + molho."),
            ("Bolinho de Queijo", "23.90", [], "8 unidades."),
        ],
    },
    {
        "name": "Saladas",
        "slug": "saladas",
        "emoji": "🥗",
        "description": "Opções leves",
        "photo_key": "salad",
        "products": [
            ("Caesar", "27.90", ["favorito"], "Frango grelhado e croutons."),
            ("Salada da Casa", "24.90", ["mais vendido"], "Mix de folhas e molho balsâmico."),
            ("Bowl Quinoa", "29.90", ["novo", "novidade"], "Quinoa, grão-de-bico e legumes."),
        ],
    },
    {
        "name": "Cafés",
        "slug": "cafes",
        "emoji": "☕",
        "description": "Café e manhã",
        "photo_key": "coffee",
        "products": [
            ("Espresso", "7.90", [], "Curto e intenso."),
            ("Cappuccino", "12.90", ["mais vendido", "favorito"], "Espuma cremosa."),
            ("Café com Leite", "9.90", ["popular"], "Clássico da manhã."),
            ("Pão na Chapa", "8.90", ["novo"], "Manteiga na medida."),
            ("Croissant", "11.90", ["novidade"], "Folhado amanteigado."),
        ],
    },
]


def _download(url: str, timeout: int = 25) -> tuple[bytes, str] | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            ctype = (resp.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip().lower()
            if ctype not in {"image/jpeg", "image/png", "image/webp"}:
                # unsplash às vezes manda octet-stream
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
    ext = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    by_type = {v: k for k, v in ext.items()}
    filename = f"{slugify(name) or 'img'}{by_type.get(content_type, '.jpg')}"
    file = ContentFile(data, name=filename)
    file.content_type = content_type
    return file


def _pick_url(photo_key: str, index: int) -> str:
    urls = PHOTO.get(photo_key) or PHOTO["burger"]
    return urls[index % len(urls)]


def _ensure_category(company: Company, spec: dict) -> Category:
    existing = Category.all_objects.filter(tenant=company, slug=spec["slug"]).first()
    if existing:
        changed = False
        for field in ("name", "emoji", "description"):
            if getattr(existing, field) != spec.get(field, getattr(existing, field)):
                setattr(existing, field, spec.get(field) or "")
                changed = True
        if changed:
            existing.is_active = True
            existing.save()
        return existing

    return Category.all_objects.create(
        tenant=company,
        name=spec["name"],
        slug=spec["slug"],
        emoji=spec.get("emoji") or "",
        description=spec.get("description") or "",
        sort_order=spec.get("sort_order", 0),
        is_active=True,
    )


def _ensure_product(
    company: Company,
    category: Category,
    name: str,
    price: str,
    tags: list[str],
    description: str,
    sort_order: int,
) -> Product:
    slug = slugify(name)
    existing = Product.all_objects.filter(tenant=company, slug=slug).first()
    if existing:
        existing.category = category
        existing.base_price = Decimal(price)
        existing.tags = tags
        existing.description = description
        existing.is_active = True
        existing.is_available = True
        existing.sort_order = sort_order
        existing.deleted_at = None
        existing.save()
        return existing

    return ProductService.create(
        tenant=company,
        data={
            "name": name,
            "slug": slug,
            "description": description,
            "base_price": Decimal(price),
            "category_id": category.id,
            "is_active": True,
            "is_available": True,
            "tags": tags,
            "sort_order": sort_order,
            "option_group_ids": [],
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
    except Exception as exc:  # noqa: BLE001 — seed local, não derruba o resto
        log(f"  ⚠ foto {product.name}: {exc}")
        return False


def _dedupe_product_images(company: Company, log: Callable[[str], None]) -> int:
    """mantém 1 foto por produto (a mais antiga como primary)."""
    removed = 0
    for product in Product.all_objects.filter(tenant=company):
        images = list(
            ProductImage.all_objects.filter(product=product).order_by("created_at", "id")
        )
        if len(images) <= 1:
            if images and not images[0].is_primary:
                images[0].is_primary = True
                images[0].save(update_fields=["is_primary", "updated_at"])
            continue
        keep = images[0]
        keep.is_primary = True
        keep.save(update_fields=["is_primary", "updated_at"])
        for extra in images[1:]:
            extra.delete()
            removed += 1
    if removed:
        log(f"fotos duplicadas removidas: {removed}")
    return removed


def _set_category_cover(category: Category, url: str, log: Callable[[str], None]) -> None:
    if category.image_url:
        return
    downloaded = _download(url)
    if not downloaded:
        return
    data, ctype = downloaded
    file = _as_image_file(data, ctype, category.slug)
    from django.core.files.storage import default_storage
    import os
    import uuid

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
                log("logo da loja atualizado")
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
                log("capa da loja atualizada")
            except Exception as exc:  # noqa: BLE001
                log(f"capa falhou: {exc}")


def _seed_campaigns(company: Company, products_by_slug: dict[str, Product], log: Callable[[str], None]) -> None:
    from apps.promotions.models import Campaign

    specs = [
        ("margherita", "29.90", 200, "Relâmpago Margherita"),
        ("smash-burger", "22.90", 100, "Smash em destaque"),
        ("combo-familia", "79.90", 100, "Combo Família especial"),
        ("brownie", "9.90", 10, "Brownie do dia"),
    ]
    now = timezone.now()
    created = 0
    for slug, promo, weight, title in specs:
        product = products_by_slug.get(slug)
        if not product:
            continue
        exists = Campaign.all_objects.filter(
            tenant=company,
            product=product,
            status="active",
        ).exists()
        if exists:
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
def seed_demo_rich(
    company: Company,
    *,
    skip_images: bool = False,
    log: Callable[[str], None] | None = None,
) -> dict:
    """Preenche o tenant com catálogo rico (idempotente por slug)."""
    log = log or (lambda msg: None)
    stats = {"categories": 0, "products": 0, "images": 0}

    TenantContext.set(company)
    try:
        SettingsService.update(company, auto_close_outside_hours=False, is_open=True)
        _branding(company, log, skip_images)
        _dedupe_product_images(company, log)

        products_by_slug: dict[str, Product] = {}

        for order, spec in enumerate(CATALOG):
            spec = {**spec, "sort_order": order}
            category = _ensure_category(company, spec)
            stats["categories"] += 1
            log(f"categoria: {category.name}")

            if not skip_images:
                _set_category_cover(category, _pick_url(spec["photo_key"], 0), log)

            for idx, (name, price, tags, description) in enumerate(spec["products"]):
                product = _ensure_product(
                    company,
                    category,
                    name,
                    price,
                    tags,
                    description,
                    sort_order=idx,
                )
                products_by_slug[product.slug] = product
                stats["products"] += 1

                if not skip_images:
                    url = _pick_url(spec["photo_key"], idx + 1)
                    if _attach_image(product, url, log):
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
