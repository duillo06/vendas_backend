"""Garante tenants/roles/pedido para e2e de autorização (Onda 4)."""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.accounts.models import Employee, EmployeeRole, Role
from apps.catalog.models import Option, Product, ProductOptionGroup
from apps.catalog.services.seed_catalog import seed_demo_catalog
from apps.companies.models import Company
from apps.companies.services.onboarding_service import OnboardingService
from apps.companies.services.settings_service import SettingsService
from apps.orders.models import Order
from apps.orders.services.order_service import OrderService


def _ensure_staff(company: Company, *, email: str, password: str, role_name: str) -> Employee:
    employee = Employee.all_objects.filter(tenant=company, email=email).first()
    if employee is None:
        employee = Employee(
            tenant=company,
            email=email,
            first_name=role_name.title(),
            last_name="E2E",
            is_owner=False,
            is_active=True,
        )
        employee.set_password(password)
        employee.save()
    else:
        employee.set_password(password)
        employee.is_active = True
        employee.is_owner = False
        employee.save(update_fields=["password_hash", "is_active", "is_owner", "updated_at"])

    role = Role.all_objects.get(tenant=company, name=role_name)
    EmployeeRole.objects.get_or_create(employee=employee, role=role)
    return employee


def _ensure_company(
    *,
    subdomain: str,
    trade_name: str,
    email: str,
    owner_email: str,
    owner_password: str,
) -> Company:
    company = Company.objects.filter(subdomain=subdomain).first()
    if company is None:
        company = OnboardingService.create_company(
            trade_name=trade_name,
            subdomain=subdomain,
            email=email,
            owner_email=owner_email,
            owner_password=owner_password,
        )
    seed_demo_catalog(company)
    SettingsService.update(company, auto_close_outside_hours=False, is_open=True)
    return company


def _checkout_order(company: Company) -> Order:
    existing = Order.all_objects.filter(tenant=company).order_by("-created_at").first()
    if existing:
        return existing

    product = Product.all_objects.get(tenant=company, slug="x-burger")
    link = (
        ProductOptionGroup.all_objects.filter(product=product)
        .select_related("option_group")
        .first()
    )
    option = Option.all_objects.filter(option_group=link.option_group).first()
    return OrderService.create_from_checkout(
        tenant=company,
        data={
            "customer_name": "Cliente E2E",
            "customer_phone": "(11) 90000-0002",
            "delivery_type": "pickup",
            "payment_method": "pix",
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": 1,
                    "options": [{"option_id": str(option.id)}],
                }
            ],
        },
    )


class Command(BaseCommand):
    help = "Seed mínimo para Playwright segurança (doc 33 Onda 4)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            default="",
            help="Caminho do JSON de fixtures (default: stdout)",
        )

    def handle(self, *args, **options):
        tenant_a = _ensure_company(
            subdomain="demo",
            trade_name="Lanchonete Demo",
            email="contato@demo.com",
            owner_email="admin@demo.com",
            owner_password="demo1234",
        )
        tenant_b = _ensure_company(
            subdomain="outra-loja",
            trade_name="Loja Beta E2E",
            email="contato@outra.com",
            owner_email="admin@outra.com",
            owner_password="outra1234",
        )

        _ensure_staff(tenant_a, email="kitchen@demo.com", password="kitchen12", role_name="kitchen")
        _ensure_staff(
            tenant_a,
            email="operator@demo.com",
            password="operator12",
            role_name="operator",
        )

        order_a = _checkout_order(tenant_a)
        order_b = _checkout_order(tenant_b)

        payload = {
            "tenant_a": {"subdomain": tenant_a.subdomain, "id": str(tenant_a.id)},
            "tenant_b": {"subdomain": tenant_b.subdomain, "id": str(tenant_b.id)},
            "owner_a": {"email": "admin@demo.com", "password": "demo1234"},
            "owner_b": {"email": "admin@outra.com", "password": "outra1234"},
            "kitchen": {"email": "kitchen@demo.com", "password": "kitchen12"},
            "operator": {"email": "operator@demo.com", "password": "operator12"},
            "order_a_id": str(order_a.id),
            "order_b_id": str(order_b.id),
        }

        out = options["out"]
        text = json.dumps(payload, indent=2)
        if out:
            path = Path(out)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text + "\n", encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"fixtures → {path}"))
        else:
            self.stdout.write(text)
