from django.db import transaction

from apps.catalog.domain.validators import (
    validate_default_option_ids,
    validate_option_group_rules,
    validate_pricing_config,
    validate_ui_config,
)
from apps.catalog.models import Option, OptionGroup, Product, ProductOptionGroup
from apps.catalog.services.catalog_cache import invalidate_catalog_cache, invalidate_product_cache


class OptionGroupService:
    @staticmethod
    def _validate_group_payload(*, group: OptionGroup | None, data: dict) -> None:
        selection_type = data.get("selection_type") or (group.selection_type if group else None)
        min_selections = data.get("min_selections", group.min_selections if group else 0)
        max_selections = data.get("max_selections", group.max_selections if group else 1)
        is_required = data.get("is_required", group.is_required if group else False)
        selection_mode = data.get("selection_mode", group.selection_mode if group else "pick")
        visibility = data.get("visibility", group.visibility if group else "always")
        ui_config = data.get("ui_config", group.ui_config if group else {})
        pricing_config = data.get("pricing_config", group.pricing_config if group else {})
        default_option_ids = data.get("default_option_ids", group.default_option_ids if group else [])

        validate_option_group_rules(
            selection_type=selection_type,
            min_selections=min_selections,
            max_selections=max_selections,
            is_required=is_required,
            selection_mode=selection_mode,
        )
        validate_pricing_config(pricing_config)
        validate_ui_config(visibility=visibility, ui_config=ui_config)

        if group is not None and default_option_ids is not None:
            validate_default_option_ids(
                option_group=group,
                default_option_ids=default_option_ids,
                max_selections=max_selections,
                selection_mode=selection_mode,
            )

    @staticmethod
    @transaction.atomic
    def create(*, tenant, data: dict) -> OptionGroup:
        OptionGroupService._validate_group_payload(group=None, data=data)
        group = OptionGroup.all_objects.create(tenant=tenant, **data)
        if data.get("default_option_ids"):
            OptionGroupService._validate_group_payload(group=group, data=data)
        invalidate_catalog_cache(tenant.id)
        return group

    @staticmethod
    @transaction.atomic
    def update(*, group: OptionGroup, data: dict) -> OptionGroup:
        for field, value in data.items():
            setattr(group, field, value)

        OptionGroupService._validate_group_payload(group=group, data=data)
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
        link, created = ProductOptionGroup.all_objects.get_or_create(
            tenant=product.tenant,
            product=product,
            option_group=option_group,
            defaults={"sort_order": sort_order},
        )
        if not created and link.sort_order != sort_order:
            link.sort_order = sort_order
            link.save(update_fields=["sort_order", "updated_at"])
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

    @staticmethod
    @transaction.atomic
    def sync_product_group_links(product: Product, links: list[dict]) -> None:
        incoming_ids = [link["option_group_id"] for link in links]
        ProductOptionGroup.all_objects.filter(product=product).exclude(
            option_group_id__in=incoming_ids,
        ).delete()

        for index, link_data in enumerate(links):
            option_group = OptionGroup.all_objects.get(
                id=link_data["option_group_id"],
                tenant=product.tenant,
            )
            link, _ = ProductOptionGroup.all_objects.update_or_create(
                tenant=product.tenant,
                product=product,
                option_group=option_group,
                defaults={
                    "sort_order": link_data.get("sort_order", index),
                    "override_min": link_data.get("override_min"),
                    "override_max": link_data.get("override_max"),
                    "override_required": link_data.get("override_required"),
                    "override_display_type": link_data.get("override_display_type") or None,
                    "override_pricing_config": link_data.get("override_pricing_config"),
                    "override_ui_config": link_data.get("override_ui_config"),
                },
            )
            link.sort_order = link_data.get("sort_order", index)
            link.override_min = link_data.get("override_min")
            link.override_max = link_data.get("override_max")
            link.override_required = link_data.get("override_required")
            link.override_display_type = link_data.get("override_display_type") or None
            link.override_pricing_config = link_data.get("override_pricing_config")
            link.override_ui_config = link_data.get("override_ui_config")
            link.save()

        invalidate_product_cache(product.tenant_id, product.slug)

    @staticmethod
    @transaction.atomic
    def reorder_groups(*, tenant, ids: list) -> None:
        groups = {
            str(group.id): group
            for group in OptionGroup.all_objects.filter(tenant=tenant, id__in=ids)
        }
        if len(groups) != len(ids):
            raise ValueError("Um ou mais grupos não foram encontrados")

        for index, group_id in enumerate(ids):
            group = groups[str(group_id)]
            group.sort_order = index

        OptionGroup.all_objects.bulk_update(groups.values(), ["sort_order", "updated_at"])
        invalidate_catalog_cache(tenant.id)

    @staticmethod
    @transaction.atomic
    def reorder_options(*, group: OptionGroup, ids: list) -> None:
        options = {
            str(option.id): option
            for option in Option.all_objects.filter(option_group=group, id__in=ids)
        }
        if len(options) != len(ids):
            raise ValueError("Uma ou mais opções não foram encontradas")

        for index, option_id in enumerate(ids):
            option = options[str(option_id)]
            option.sort_order = index

        Option.all_objects.bulk_update(options.values(), ["sort_order", "updated_at"])
        invalidate_catalog_cache(group.tenant_id)

    @staticmethod
    @transaction.atomic
    def reorder_product_groups(*, product: Product, ids: list) -> None:
        links = {
            str(link.option_group_id): link
            for link in ProductOptionGroup.all_objects.filter(product=product, option_group_id__in=ids)
        }
        if len(links) != len(ids):
            raise ValueError("Um ou mais vínculos não foram encontrados")

        for index, group_id in enumerate(ids):
            link = links[str(group_id)]
            link.sort_order = index

        ProductOptionGroup.all_objects.bulk_update(links.values(), ["sort_order", "updated_at"])
        invalidate_product_cache(product.tenant_id, product.slug)

    @staticmethod
    @transaction.atomic
    def duplicate_group(*, group: OptionGroup) -> OptionGroup:
        new_group = OptionGroup.all_objects.create(
            tenant=group.tenant,
            name=f"{group.name} (cópia)",
            description=group.description,
            selection_type=group.selection_type,
            selection_mode=group.selection_mode,
            display_type=group.display_type,
            min_selections=group.min_selections,
            max_selections=group.max_selections,
            is_required=group.is_required,
            sort_order=group.sort_order + 1,
            is_active=group.is_active,
            icon=group.icon,
            image_url=group.image_url,
            visibility=group.visibility,
            pricing_config=group.pricing_config or {"strategy": "additive"},
            ui_config=group.ui_config or {},
            default_option_ids=[],
        )

        for option in group.options.all().order_by("sort_order", "name"):
            Option.all_objects.create(
                tenant=group.tenant,
                option_group=new_group,
                name=option.name,
                description=option.description,
                price_modifier=option.price_modifier,
                price_type=option.price_type,
                is_active=option.is_active,
                is_available=option.is_available,
                sort_order=option.sort_order,
                image_url=option.image_url,
                icon=option.icon,
                stock_quantity=option.stock_quantity,
                metadata=option.metadata,
            )

        invalidate_catalog_cache(group.tenant_id)
        return new_group

    @staticmethod
    @transaction.atomic
    def duplicate_option(*, option: Option) -> Option:
        new_option = Option.all_objects.create(
            tenant=option.tenant,
            option_group=option.option_group,
            name=f"{option.name} (cópia)",
            description=option.description,
            price_modifier=option.price_modifier,
            price_type=option.price_type,
            is_active=option.is_active,
            is_available=option.is_available,
            sort_order=option.sort_order + 1,
            image_url=option.image_url,
            icon=option.icon,
            stock_quantity=option.stock_quantity,
            metadata=option.metadata,
        )
        invalidate_catalog_cache(option.tenant_id)
        return new_option
