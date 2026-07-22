# permissões do MVP + extras da matriz do doc 08
ALL_PERMISSIONS = [
    "dashboard.view",
    "orders.view",
    "orders.manage",
    "orders.update_status",
    "catalog.view",
    "catalog.manage",
    "customers.view",
    "customers.manage",
    "promotions.manage",
    "settings.manage",
    "employees.manage",
    "reports.view",
]

SYSTEM_ROLES = {
    "owner": {
        "display_name": "Dono",
        "permissions": ALL_PERMISSIONS,
    },
    "manager": {
        "display_name": "Gerente",
        "permissions": [
            "dashboard.view",
            "orders.view",
            "orders.manage",
            "orders.update_status",
            "catalog.view",
            "catalog.manage",
            "customers.view",
            "customers.manage",
            "promotions.manage",
            "reports.view",
        ],
    },
    "operator": {
        "display_name": "Operador",
        "permissions": [
            "dashboard.view",
            "orders.view",
            "orders.manage",
            "orders.update_status",
            "catalog.view",
            "customers.view",
        ],
    },
    "kitchen": {
        "display_name": "Cozinha",
        "permissions": [
            "orders.view",
            "orders.update_status",
        ],
    },
}

TOKEN_BLACKLIST_PREFIX = "jwt_blacklist:"
