from contextvars import ContextVar
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    pass

_tenant: ContextVar[Any | None] = ContextVar("tenant", default=None)


class TenantContext:
    @staticmethod
    def set(tenant: Any) -> None:
        _tenant.set(tenant)

    @staticmethod
    def get() -> Any:
        tenant = _tenant.get()
        if tenant is None:
            raise RuntimeError("Tenant context not set")
        return tenant

    @staticmethod
    def get_id() -> UUID:
        tenant = TenantContext.get()
        return tenant.id

    @staticmethod
    def clear() -> None:
        _tenant.set(None)
