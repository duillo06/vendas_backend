"""Enche o tenant com pedidos espalhados no tempo — pra ver o Dashboard V1."""

from __future__ import annotations

import random
import zoneinfo
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Product
from apps.catalog.services.seed_catalog import seed_demo_catalog
from apps.companies.models import Company
from apps.companies.services.onboarding_service import OnboardingService
from apps.customers.models import Customer
from apps.orders.domain.enums import DeliveryType, OrderSource, OrderStatus, PaymentMethod, PaymentStatus
from apps.orders.models import Order, OrderItem, OrderPayment

SEED_TAG = "seed_dashboard"
FIRST_NAMES = [
    "Maria",
    "João",
    "Ana",
    "Pedro",
    "Carla",
    "Lucas",
    "Juliana",
    "Rafael",
    "Fernanda",
    "Bruno",
    "Camila",
    "Diego",
    "Patrícia",
    "Thiago",
    "Larissa",
    "Gustavo",
    "Beatriz",
    "Felipe",
    "Amanda",
    "Rodrigo",
]
LAST_NAMES = [
    "Silva",
    "Santos",
    "Oliveira",
    "Souza",
    "Lima",
    "Costa",
    "Ferreira",
    "Almeida",
    "Pereira",
    "Rodrigues",
]

# peso por dia da semana (0=seg … 6=dom) — domingo e sábado mais fortes
WEEKDAY_WEIGHT = [0.7, 0.65, 0.8, 0.85, 1.0, 1.25, 1.45]

# faixa horária → peso (pico jantar + almoço)
HOUR_WEIGHT = {
    10: 0.3,
    11: 0.7,
    12: 1.2,
    13: 1.1,
    14: 0.5,
    15: 0.25,
    16: 0.3,
    17: 0.6,
    18: 1.4,
    19: 1.6,
    20: 1.5,
    21: 1.1,
    22: 0.6,
    23: 0.2,
}

PAYMENT_WEIGHTS = [
    (PaymentMethod.PIX, 0.38),
    (PaymentMethod.CARD_ON_DELIVERY, 0.42),
    (PaymentMethod.CASH, 0.20),
]

PRODUCT_NAMES_FALLBACK = [
    ("Pizza Calabresa", Decimal("49.90")),
    ("Pizza Mussarela", Decimal("44.90")),
    ("X-Burger", Decimal("28.90")),
    ("Coca-Cola 2L", Decimal("12.00")),
    ("Guaraná 2L", Decimal("11.00")),
]


class Command(BaseCommand):
    help = "Gera muitos pedidos no tenant demo para visualizar o Dashboard V1"

    def add_arguments(self, parser):
        parser.add_argument("--subdomain", default="demo", help="Tenant alvo (default: demo)")
        parser.add_argument(
            "--days",
            type=int,
            default=35,
            help="Quantos dias pra trás espalhar (default: 35)",
        )
        parser.add_argument(
            "--per-day",
            type=int,
            default=14,
            help="Média base de pedidos/dia antes dos pesos (default: 14)",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Apaga pedidos anteriores deste seed (tag seed_dashboard) antes de criar",
        )
        parser.add_argument("--seed", type=int, default=42, help="Seed do random (reprodutível)")

    def handle(self, *args, **options):
        random.seed(options["seed"])
        subdomain = options["subdomain"]
        days = options["days"]
        per_day = options["per_day"]

        company = self._ensure_company(subdomain)
        products = self._ensure_products(company)
        customers = self._ensure_customers(company, count=24)

        if options["reset"]:
            deleted = self._reset_seed_orders(company)
            self.stdout.write(f"Removidos {deleted} pedidos do seed anterior.")

        next_num = self._next_order_number(company)
        tz = zoneinfo.ZoneInfo(company.timezone)
        today = timezone.now().astimezone(tz).date()

        created = 0
        with transaction.atomic():
            for offset in range(days):
                day = today - timedelta(days=offset)
                target = self._orders_for_day(day, per_day, is_today=offset == 0)
                for _ in range(target):
                    when = self._pick_datetime(day, tz, is_today=offset == 0)
                    status = self._pick_status(is_today=offset == 0)
                    customer = random.choice(customers)
                    product = random.choice(products)
                    qty = random.choice([1, 1, 1, 2])
                    unit = Decimal(str(product["price"]))
                    subtotal = (unit * qty).quantize(Decimal("0.01"))
                    delivery = random.choice(
                        [DeliveryType.DELIVERY, DeliveryType.DELIVERY, DeliveryType.PICKUP]
                    )
                    fee = Decimal("8.00") if delivery == DeliveryType.DELIVERY else Decimal("0")
                    if status == OrderStatus.CANCELLED and random.random() < 0.3:
                        fee = Decimal("0")
                    total = (subtotal + fee).quantize(Decimal("0.01"))
                    payment_method = self._pick_payment()

                    order = Order.all_objects.create(
                        tenant=company,
                        customer=customer,
                        order_number=f"#{next_num:04d}",
                        status=status,
                        delivery_type=delivery,
                        subtotal=subtotal,
                        discount=Decimal("0"),
                        delivery_fee=fee,
                        total=total,
                        customer_name=f"{customer.first_name} {customer.last_name}".strip(),
                        customer_phone=customer.phone,
                        notes="",
                        internal_notes=SEED_TAG,
                        source=OrderSource.STOREFRONT,
                        confirmed_at=when if status != OrderStatus.PENDING else None,
                        completed_at=when if status == OrderStatus.COMPLETED else None,
                        cancelled_at=when if status == OrderStatus.CANCELLED else None,
                        cancellation_reason="Cliente desistiu" if status == OrderStatus.CANCELLED else "",
                    )
                    OrderItem.all_objects.create(
                        tenant=company,
                        order=order,
                        product_id=product.get("id"),
                        product_name=product["name"],
                        unit_price=unit,
                        quantity=qty,
                        total_price=subtotal,
                    )
                    if status != OrderStatus.CANCELLED:
                        OrderPayment.all_objects.create(
                            tenant=company,
                            order=order,
                            method=payment_method,
                            status=PaymentStatus.PAID
                            if status == OrderStatus.COMPLETED
                            else PaymentStatus.PENDING,
                            amount=total,
                            paid_at=when if status == OrderStatus.COMPLETED else None,
                        )

                    # backdate — auto_now_add ignora no create
                    Order.all_objects.filter(pk=order.pk).update(
                        created_at=when,
                        updated_at=when,
                        confirmed_at=order.confirmed_at,
                        completed_at=order.completed_at,
                        cancelled_at=order.cancelled_at,
                    )
                    OrderItem.all_objects.filter(order=order).update(created_at=when, updated_at=when)
                    OrderPayment.all_objects.filter(order=order).update(created_at=when, updated_at=when)

                    next_num += 1
                    created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"OK — {created} pedidos em '{subdomain}' "
                f"({days} dias, ~{per_day}/dia base). Atualiza o dashboard."
            )
        )

    def _ensure_company(self, subdomain: str) -> Company:
        company = Company.objects.filter(subdomain=subdomain).first()
        if company:
            return company
        if subdomain != "demo":
            raise CommandError(f"Tenant '{subdomain}' não existe.")
        company = OnboardingService.create_company(
            trade_name="Lanchonete Demo",
            subdomain="demo",
            email="contato@demo.com",
            phone="(11) 99999-0000",
            owner_email="admin@demo.com",
            owner_password="demo1234",
            owner_first_name="Admin",
            owner_last_name="Demo",
        )
        seed_demo_catalog(company)
        self.stdout.write("Tenant demo criado + cardápio.")
        return company

    def _ensure_products(self, company: Company) -> list[dict]:
        qs = list(
            Product.all_objects.filter(tenant=company, is_available=True, deleted_at__isnull=True)[:20]
        )
        if not qs:
            seed_demo_catalog(company)
            qs = list(
                Product.all_objects.filter(tenant=company, is_available=True, deleted_at__isnull=True)[:20]
            )
        if qs:
            return [
                {"id": p.id, "name": p.name, "price": p.base_price}
                for p in qs
            ]
        return [{"id": None, "name": n, "price": p} for n, p in PRODUCT_NAMES_FALLBACK]

    def _ensure_customers(self, company: Company, count: int) -> list[Customer]:
        existing = list(Customer.all_objects.filter(tenant=company, deleted_at__isnull=True)[:count])
        if len(existing) >= min(8, count):
            return existing

        created = []
        for i in range(count):
            phone = f"1199{i:06d}"
            customer, _ = Customer.all_objects.get_or_create(
                tenant=company,
                phone=phone,
                defaults={
                    "first_name": FIRST_NAMES[i % len(FIRST_NAMES)],
                    "last_name": LAST_NAMES[i % len(LAST_NAMES)],
                    "email": f"cliente{i}@demo.local",
                    "is_active": True,
                },
            )
            created.append(customer)
        return created

    def _reset_seed_orders(self, company: Company) -> int:
        qs = Order.all_objects.filter(tenant=company, internal_notes=SEED_TAG)
        count = qs.count()
        qs.delete()
        return count

    def _next_order_number(self, company: Company) -> int:
        max_num = 0
        for raw in (
            Order.all_objects.filter(tenant=company)
            .values_list("order_number", flat=True)
            .iterator(chunk_size=500)
        ):
            try:
                max_num = max(max_num, int(str(raw).lstrip("#")))
            except (TypeError, ValueError):
                continue
        return max_num + 1

    def _orders_for_day(self, day, per_day: int, *, is_today: bool) -> int:
        weight = WEEKDAY_WEIGHT[day.weekday()]
        # dias recentes um pouco mais cheios (tendência positiva no gráfico)
        age_boost = 1.0 + max(0, (10 - (timezone.now().date() - day).days)) * 0.03
        base = per_day * weight * age_boost
        n = max(2, int(round(random.gauss(base, base * 0.18))))
        if is_today:
            # hoje ainda em andamento — um pouco menos que o pico fechado
            n = max(4, int(n * 0.75))
        return n

    def _pick_datetime(self, day, tz, *, is_today: bool) -> datetime:
        hours = list(HOUR_WEIGHT.keys())
        weights = [HOUR_WEIGHT[h] for h in hours]
        hour = random.choices(hours, weights=weights, k=1)[0]
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        when = datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=tz)
        now = timezone.now().astimezone(tz)
        if is_today and when > now:
            when = now - timedelta(minutes=random.randint(5, 90))
        return when

    def _pick_status(self, *, is_today: bool) -> str:
        if is_today:
            return random.choices(
                [
                    OrderStatus.COMPLETED,
                    OrderStatus.PENDING,
                    OrderStatus.PREPARING,
                    OrderStatus.READY,
                    OrderStatus.CANCELLED,
                ],
                weights=[0.45, 0.18, 0.18, 0.12, 0.07],
                k=1,
            )[0]
        return random.choices(
            [OrderStatus.COMPLETED, OrderStatus.CANCELLED],
            weights=[0.93, 0.07],
            k=1,
        )[0]

    def _pick_payment(self) -> str:
        methods, weights = zip(*PAYMENT_WEIGHTS)
        return random.choices(methods, weights=weights, k=1)[0]
