from django.utils.text import slugify


def make_unique_slug(model_cls, tenant_id, base: str, *, exclude_id=None) -> str:
    slug_base = slugify(base) or "item"
    slug = slug_base
    counter = 2

    qs = model_cls.all_objects.filter(tenant_id=tenant_id, slug=slug)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    while qs.exists():
        slug = f"{slug_base}-{counter}"
        counter += 1
        qs = model_cls.all_objects.filter(tenant_id=tenant_id, slug=slug)
        if exclude_id:
            qs = qs.exclude(id=exclude_id)

    return slug
