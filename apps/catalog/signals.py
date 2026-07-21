from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.catalog.models import (
    Category,
    Option,
    OptionGroup,
    Product,
    ProductComposition,
    ProductImage,
    ProductOptionGroup,
)
from apps.catalog.services.catalog_cache import invalidate_catalog_cache, invalidate_product_cache


def _invalidate_product(sender, instance, **kwargs):
    if hasattr(instance, "slug"):
        invalidate_product_cache(instance.tenant_id, instance.slug)
    else:
        invalidate_catalog_cache(instance.tenant_id)


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
def category_cache_signal(sender, instance, **kwargs):
    invalidate_catalog_cache(instance.tenant_id)


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
def product_cache_signal(sender, instance, **kwargs):
    _invalidate_product(sender, instance, **kwargs)


@receiver(post_save, sender=ProductImage)
@receiver(post_delete, sender=ProductImage)
def product_image_cache_signal(sender, instance, **kwargs):
    invalidate_product_cache(instance.tenant_id, instance.product.slug)


@receiver(post_save, sender=ProductComposition)
@receiver(post_delete, sender=ProductComposition)
def composition_cache_signal(sender, instance, **kwargs):
    # senão o cardápio continua sem meio a meio até o cache expirar
    invalidate_product_cache(instance.tenant_id, instance.product.slug)


@receiver(post_save, sender=OptionGroup)
@receiver(post_delete, sender=OptionGroup)
@receiver(post_save, sender=Option)
@receiver(post_delete, sender=Option)
@receiver(post_save, sender=ProductOptionGroup)
@receiver(post_delete, sender=ProductOptionGroup)
def option_cache_signal(sender, instance, **kwargs):
    invalidate_catalog_cache(instance.tenant_id)
