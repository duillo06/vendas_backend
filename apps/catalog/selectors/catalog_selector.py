import os
import uuid

from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db.models import Count, Prefetch, Q

from apps.catalog.domain.exceptions import ImageLimitExceeded
from apps.catalog.domain.validators import validate_product_image
from apps.catalog.models import (
    Category,
    Option,
    Product,
    ProductImage,
    ProductOptionGroup,
)
from apps.catalog.services.catalog_cache import invalidate_product_cache
from core.cache.keys import tenant_key

CACHE_TTL = 300


class CatalogSelector:
    @staticmethod
    def get_categories(tenant_id):
        key = tenant_key(str(tenant_id), "catalog", "categories")
        cached = cache.get(key)
        if cached is not None:
            return cached

        categories = list(
            Category.objects.filter(is_active=True)
            .annotate(
                product_count=Count(
                    "products",
                    filter=Q(products__is_active=True, products__deleted_at__isnull=True),
                ),
            )
            .order_by("sort_order", "name"),
        )
        cache.set(key, categories, timeout=CACHE_TTL)
        return categories

    @staticmethod
    def get_active_products(*, category_slug: str | None = None, search: str | None = None):
        qs = (
            Product.objects.filter(is_active=True, is_available=True)
            .select_related("category")
            .prefetch_related("images")
            .annotate(option_groups_count=Count("product_option_groups"))
        )

        if category_slug:
            qs = qs.filter(category__slug=category_slug, category__is_active=True)

        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(tags__icontains=search),
            )

        return qs.order_by("sort_order", "name")

    @staticmethod
    def get_product_detail(*, tenant_id, slug: str) -> Product:
        key = tenant_key(str(tenant_id), "catalog", "product", slug)
        cached = cache.get(key)
        if cached is not None:
            return cached

        product = (
            Product.objects.filter(slug=slug, is_active=True)
            .select_related("category", "composition")
            .prefetch_related(
                "images",
                Prefetch(
                    "product_option_groups",
                    queryset=ProductOptionGroup.objects.select_related("option_group")
                    .filter(option_group__is_active=True)
                    .prefetch_related(
                        Prefetch(
                            "option_group__options",
                            queryset=Option.objects.filter(is_active=True).order_by("sort_order"),
                        ),
                    )
                    .order_by("sort_order"),
                ),
            )
            .get()
        )
        cache.set(key, product, timeout=CACHE_TTL)
        return product


class ProductImageService:
    MAX_IMAGES = 5

    @staticmethod
    def add_image(*, product: Product, image_file, alt_text: str = "", is_primary: bool = False):
        validate_product_image(image_file)

        if product.images.count() >= ProductImageService.MAX_IMAGES:
            raise ImageLimitExceeded()

        ext = os.path.splitext(image_file.name)[1] or ".jpg"
        # path relativo ao MEDIA_ROOT — sem prefixo "media/" (senão vira /media/media/...)
        filename = f"{product.tenant_id}/products/{uuid.uuid4()}{ext}"
        saved_path = default_storage.save(filename, image_file)
        image_url = default_storage.url(saved_path)

        if is_primary:
            product.images.update(is_primary=False)

        image = ProductImage.all_objects.create(
            tenant=product.tenant,
            product=product,
            image_url=image_url,
            alt_text=alt_text or product.name,
            is_primary=is_primary or product.images.count() == 0,
            sort_order=product.images.count(),
        )
        invalidate_product_cache(product.tenant_id, product.slug)
        return image

    @staticmethod
    def set_primary_image(*, product: Product, image_id) -> ProductImage:
        image = product.images.get(id=image_id)
        product.images.update(is_primary=False)
        image.is_primary = True
        image.save(update_fields=["is_primary", "updated_at"])
        invalidate_product_cache(product.tenant_id, product.slug)
        return image

    @staticmethod
    def delete_image(*, product: Product, image_id) -> None:
        image = product.images.get(id=image_id)
        was_primary = image.is_primary
        image.delete()

        if was_primary:
            next_image = product.images.order_by("sort_order", "created_at").first()
            if next_image:
                next_image.is_primary = True
                next_image.save(update_fields=["is_primary", "updated_at"])

        invalidate_product_cache(product.tenant_id, product.slug)
