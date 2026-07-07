from django.db import models

from core.tenancy.context import TenantContext


class TenantQuerySet(models.QuerySet):
    def for_tenant(self, tenant_id):
        return self.filter(tenant_id=tenant_id)


class TenantManager(models.Manager):
    def get_queryset(self):
        qs = TenantQuerySet(self.model, using=self._db)
        try:
            tenant_id = TenantContext.get_id()
        except RuntimeError:
            return qs.none()
        return qs.filter(tenant_id=tenant_id)
