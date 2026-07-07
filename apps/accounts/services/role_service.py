from apps.accounts.domain.constants import SYSTEM_ROLES
from apps.accounts.models import Role, RolePermission


class RoleService:
    @staticmethod
    def create_system_roles(company) -> dict[str, Role]:
        roles: dict[str, Role] = {}

        for name, config in SYSTEM_ROLES.items():
            role, _ = Role.all_objects.get_or_create(
                tenant=company,
                name=name,
                defaults={
                    "display_name": config["display_name"],
                    "is_system": True,
                },
            )
            RoleService._sync_permissions(role, config["permissions"])
            roles[name] = role

        return roles

    @staticmethod
    def _sync_permissions(role: Role, permissions: list[str]) -> None:
        current = set(role.permissions.values_list("permission", flat=True))
        desired = set(permissions)

        for permission in desired - current:
            RolePermission.objects.create(role=role, permission=permission)

        role.permissions.exclude(permission__in=desired).delete()
