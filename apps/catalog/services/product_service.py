from django.db import transaction
from django.utils import timezone

from apps.catalog.domain.exceptions import CategoryHasActiveProducts
from apps.catalog.models import Category, Product
from apps.catalog.services.catalog_cache import invalidate_catalog_cache
from core.utils.slug import make_unique_slug


class ProductService:
    @staticmethod
    @transaction.atomic
    def create(*, tenant, data: dict) -> Product:
        option_group_ids = data.pop("option_group_ids", None)
        slug = data.pop("slug", None) or make_unique_slug(Product, tenant.id, data["name"])

        product = Product.all_objects.create(
            tenant=tenant,
            slug=slug,
            **data,
        )

        if option_group_ids is not None:
            from apps.catalog.services.option_group_service import OptionGroupService

            OptionGroupService.sync_product_groups(product, option_group_ids)

        invalidate_catalog_cache(tenant.id)
        return product

    @staticmethod
    @transaction.atomic
    def update(*, product: Product, data: dict) -> Product:
        option_group_ids = data.pop("option_group_ids", None)

        for field, value in data.items():
            setattr(product, field, value)

        if "name" in data and "slug" not in data:
            product.slug = make_unique_slug(
                Product,
                product.tenant_id,
                product.name,
                exclude_id=product.id,
            )

        product.save()

        if option_group_ids is not None:
            from apps.catalog.services.option_group_service import OptionGroupService

            OptionGroupService.sync_product_groups(product, option_group_ids)

        from apps.catalog.services.catalog_cache import invalidate_product_cache

        invalidate_product_cache(product.tenant_id, product.slug)
        return product

    @staticmethod
    @transaction.atomic
    def soft_delete(product: Product) -> None:
        product.deleted_at = timezone.now()
        product.is_active = False
        product.save(update_fields=["deleted_at", "is_active", "updated_at"])

        from apps.catalog.services.catalog_cache import invalidate_product_cache

        invalidate_product_cache(product.tenant_id, product.slug)

    @staticmethod
    def get_by_slug(slug: str) -> Product:
        return Product.objects.select_related("category").get(slug=slug, is_active=True)


class CategoryService:
    @staticmethod
    @transaction.atomic
    def create(*, tenant, data: dict) -> Category:
        slug = data.pop("slug", None) or make_unique_slug(Category, tenant.id, data["name"])
        data.pop("product_count", None)
        category = Category.all_objects.create(tenant=tenant, slug=slug, **data)
        invalidate_catalog_cache(tenant.id)
        return category

    @staticmethod
    @transaction.atomic
    def update(*, category: Category, data: dict) -> Category:
        for field, value in data.items():
            if field == "product_count":
                continue
            setattr(category, field, value)

        if "name" in data and "slug" not in data:
            category.slug = make_unique_slug(
                Category,
                category.tenant_id,
                category.name,
                exclude_id=category.id,
            )

        category.save()
        invalidate_catalog_cache(category.tenant_id)
        return category

    @staticmethod
    @transaction.atomic
    def soft_delete(category: Category) -> None:
        has_active_products = Product.objects.filter(
            category=category,
            is_active=True,
            deleted_at__isnull=True,
        ).exists()

        if has_active_products:
            raise CategoryHasActiveProducts()

        category.deleted_at = timezone.now()
        category.is_active = False
        category.save(update_fields=["deleted_at", "is_active", "updated_at"])
        invalidate_catalog_cache(category.tenant_id)
