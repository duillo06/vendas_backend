"""Preferências do funcionário — dashboard e afins."""

from __future__ import annotations

from copy import deepcopy

from apps.accounts.models import Employee

DEFAULT_DASHBOARD_WIDGET_ORDER = [
    "top_products",
    "hours",
    "days",
    "payments",
    "slow_products",
    "delivery",
    "customers",
]

ALLOWED_DASHBOARD_WIDGETS = frozenset(DEFAULT_DASHBOARD_WIDGET_ORDER)


class PreferencesService:
    @staticmethod
    def get(employee: Employee) -> dict:
        raw = employee.preferences if isinstance(employee.preferences, dict) else {}
        dashboard = raw.get("dashboard") if isinstance(raw.get("dashboard"), dict) else {}
        order = PreferencesService._normalize_order(dashboard.get("widget_order"))
        hidden = PreferencesService._normalize_hidden(dashboard.get("hidden_widgets"), order)
        return {
            "dashboard": {
                "widget_order": order,
                "hidden_widgets": hidden,
            }
        }

    @staticmethod
    def update(employee: Employee, patch: dict) -> dict:
        current = PreferencesService.get(employee)
        next_prefs = deepcopy(current)

        dash_patch = patch.get("dashboard")
        if isinstance(dash_patch, dict):
            if "widget_order" in dash_patch:
                next_prefs["dashboard"]["widget_order"] = PreferencesService._normalize_order(
                    dash_patch.get("widget_order")
                )
            if "hidden_widgets" in dash_patch:
                order = next_prefs["dashboard"]["widget_order"]
                next_prefs["dashboard"]["hidden_widgets"] = PreferencesService._normalize_hidden(
                    dash_patch.get("hidden_widgets"), order
                )

        employee.preferences = next_prefs
        employee.save(update_fields=["preferences", "updated_at"])
        return next_prefs

    @staticmethod
    def _normalize_order(raw) -> list[str]:
        if not isinstance(raw, list):
            return list(DEFAULT_DASHBOARD_WIDGET_ORDER)
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in raw:
            if not isinstance(item, str):
                continue
            if item not in ALLOWED_DASHBOARD_WIDGETS or item in seen:
                continue
            seen.add(item)
            cleaned.append(item)
        for widget_id in DEFAULT_DASHBOARD_WIDGET_ORDER:
            if widget_id not in seen:
                cleaned.append(widget_id)
        return cleaned

    @staticmethod
    def _normalize_hidden(raw, order: list[str]) -> list[str]:
        if not isinstance(raw, list):
            return []
        allowed = set(order)
        seen: set[str] = set()
        out: list[str] = []
        for item in raw:
            if not isinstance(item, str) or item not in allowed or item in seen:
                continue
            # não esconde todos — deixa pelo menos 1
            if len(out) >= len(order) - 1:
                break
            seen.add(item)
            out.append(item)
        return out
