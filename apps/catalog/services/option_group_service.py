from django.db import transaction

from apps.catalog.domain.validators import validate_option_group_rules
from apps.catalog.models import Option, OptionGroup, Product, ProductOptionGroup
from apps.catalog.services.catalog_cache import invalidate_catalog_cache, invalidate_product_cache


class OptionGroupService:
    @staticmethod
    @transaction.atomic
    def create(*, tenant, data: dict) -> OptionGroup:
        validate_option_group_rules(
            selection_type=data["selection_type"],
            min_selections=data.get("min_selections", 0),
            max_selections=data.get("max_selections", 1),
            is_required=data.get("is_required", False),
        )
        group = OptionGroup.all_objects.create(tenant=tenant, **data)
        invalidate_catalog_cache(tenant.id)
        return group

    @staticmethod
    @transaction.atomic
    def update(*, group: OptionGroup, data: dict) -> OptionGroup:
        for field, value in data.items():
            setattr(group, field, value)

        validate_option_group_rules(
            selection_type=group.selection_type,
            min_selections=group.min_selections,
            max_selections=group.max_selections,
            is_required=group.is_required,
        )
        group.save()
        invalidate_catalog_cache(group.tenant_id)
        return group

    @staticmethod
    @transaction.atomic
    def create_option(*, group: OptionGroup, data: dict) -> Option:
        option = Option.all_objects.create(tenant=group.tenant, option_group=group, **data)
        invalidate_catalog_cache(group.tenant_id)
        return option

    @staticmethod
    @transaction.atomic
    def update_option(*, option: Option, data: dict) -> Option:
        for field, value in data.items():
            setattr(option, field, value)
        option.save()
        invalidate_catalog_cache(option.tenant_id)
        return option

    @staticmethod
    @transaction.atomic
    def delete_option(option: Option) -> None:
        tenant_id = option.tenant_id
        option.delete()
        invalidate_catalog_cache(tenant_id)

    @staticmethod
    @transaction.atomic
    def delete(group: OptionGroup) -> None:
        tenant_id = group.tenant_id
        group.delete()
        invalidate_catalog_cache(tenant_id)

    @staticmethod
    @transaction.atomic
    def attach_to_product(*, product: Product, option_group: OptionGroup, sort_order: int = 0):
        ProductOptionGroup.all_objects.get_or_create(
            tenant=product.tenant,
            product=product,
            option_group=option_group,
            defaults={"sort_order": sort_order},
        )
        invalidate_product_cache(product.tenant_id, product.slug)

    @staticmethod
    @transaction.atomic
    def sync_product_groups(product: Product, option_group_ids: list) -> None:
        ProductOptionGroup.all_objects.filter(product=product).exclude(
            option_group_id__in=option_group_ids,
        ).delete()

        for index, group_id in enumerate(option_group_ids):
            OptionGroupService.attach_to_product(
                product=product,
                option_group=OptionGroup.all_objects.get(id=group_id, tenant=product.tenant),
                sort_order=index,
            )
