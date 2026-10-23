from __future__ import annotations

import zoneinfo
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone

from apps.catalog.models import Product
from apps.companies.models import Company
from apps.orders.domain.enums import DeliveryType, OrderStatus, PaymentMethod
from apps.orders.models import Order, OrderItem, OrderPayment

PERIOD_TODAY = "today"
PERIOD_7D = "7d"
PERIOD_30D = "30d"
PERIOD_CUSTOM = "custom"
VALID_PERIODS = {PERIOD_TODAY, PERIOD_7D, PERIOD_30D, PERIOD_CUSTOM}

# faixas de 2h pra gráfico de horário
HOUR_SLOTS = [(h, h + 2) for h in range(0, 24, 2)]

PAYMENT_LABELS = {
    PaymentMethod.CASH: "Dinheiro",
    PaymentMethod.PIX: "Pix",
    PaymentMethod.CARD_ON_DELIVERY: "Cartão na entrega",
}

DELIVERY_LABELS = {
    DeliveryType.DELIVERY: "Entrega",
    DeliveryType.PICKUP: "Retirada",
    DeliveryType.DINE_IN: "No local",
}

WEEKDAY_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


class DashboardService:
    @staticmethod
    def _tenant_today(company: Company) -> date:
        tz = zoneinfo.ZoneInfo(company.timezone)
        return timezone.now().astimezone(tz).date()

    @staticmethod
    def _tz(company: Company):
        return zoneinfo.ZoneInfo(company.timezone)

    @staticmethod
    def _day_bounds(company: Company, day: date) -> tuple[datetime, datetime]:
        tz = DashboardService._tz(company)
        start = datetime.combine(day, time.min, tzinfo=tz)
        end = datetime.combine(day, time.max, tzinfo=tz)
        return start, end

    @staticmethod
    def _range_bounds(company: Company, start_day: date, end_day: date) -> tuple[datetime, datetime]:
        start, _ = DashboardService._day_bounds(company, start_day)
        _, end = DashboardService._day_bounds(company, end_day)
        return start, end

    @staticmethod
    def _period_windows(
        company: Company,
        period: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> tuple[date, date, date, date, str]:
        today = DashboardService._tenant_today(company)
        if period == PERIOD_CUSTOM and from_date and to_date:
            cur_start, cur_end = from_date, to_date
            span = (cur_end - cur_start).days + 1
            prev_end = cur_start - timedelta(days=1)
            prev_start = prev_end - timedelta(days=span - 1)
            return cur_start, cur_end, prev_start, prev_end, "previous_custom"
        if period == PERIOD_TODAY:
            return today, today, today - timedelta(days=1), today - timedelta(days=1), "yesterday"
        if period == PERIOD_7D:
            cur_end = today
            cur_start = today - timedelta(days=6)
            prev_end = cur_start - timedelta(days=1)
            prev_start = prev_end - timedelta(days=6)
            return cur_start, cur_end, prev_start, prev_end, "previous_7d"
        # 30d (default multi-day)
        cur_end = today
        cur_start = today - timedelta(days=29)
        prev_end = cur_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=29)
        return cur_start, cur_end, prev_start, prev_end, "previous_30d"

    @staticmethod
    def _orders_qs(company: Company, start: datetime, end: datetime):
        return Order.all_objects.filter(
            tenant=company,
            created_at__gte=start,
            created_at__lte=end,
        )

    @staticmethod
    def _day_summary(company: Company, day: date) -> dict:
        # agregado do dia no fuso da loja
        start, end = DashboardService._day_bounds(company, day)
        return DashboardService._range_summary(company, start, end, day.isoformat())

    @staticmethod
    def _range_summary(company: Company, start: datetime, end: datetime, date_label: str) -> dict:
        qs = DashboardService._orders_qs(company, start, end)
        counts = qs.aggregate(
            total_orders=Count("id"),
            pending_orders=Count("id", filter=Q(status=OrderStatus.PENDING)),
            preparing_orders=Count("id", filter=Q(status=OrderStatus.PREPARING)),
            completed_orders=Count("id", filter=Q(status=OrderStatus.COMPLETED)),
            cancelled_orders=Count("id", filter=Q(status=OrderStatus.CANCELLED)),
            revenue=Sum("total", filter=Q(status=OrderStatus.COMPLETED)),
        )
        total_orders = counts["total_orders"] or 0
        revenue = counts["revenue"] or Decimal("0")
        completed_orders = counts["completed_orders"] or 0
        average_ticket = float(revenue / completed_orders) if completed_orders else 0.0
        return {
            "date": date_label,
            "total_orders": total_orders,
            "pending_orders": counts["pending_orders"] or 0,
            "preparing_orders": counts["preparing_orders"] or 0,
            "completed_orders": completed_orders,
            "cancelled_orders": counts["cancelled_orders"] or 0,
            "revenue": float(revenue),
            "average_ticket": round(average_ticket, 2),
        }

    @staticmethod
    def _delta_pct(value: float, previous: float) -> float | None:
        if previous == 0:
            return None
        return round(((value - previous) / previous) * 100, 2)

    @staticmethod
    def _build_kpis(current: dict, previous: dict) -> dict:
        cur_total = current["total_orders"]
        prev_total = previous["total_orders"]
        cur_rate = (
            round((current["cancelled_orders"] / cur_total) * 100, 2) if cur_total else 0.0
        )
        prev_rate = (
            round((previous["cancelled_orders"] / prev_total) * 100, 2) if prev_total else 0.0
        )
        return {
            "orders": {
                "value": current["total_orders"],
                "previous": previous["total_orders"],
                "delta_pct": DashboardService._delta_pct(
                    current["total_orders"], previous["total_orders"]
                ),
            },
            "revenue": {
                "value": current["revenue"],
                "previous": previous["revenue"],
                "delta_pct": DashboardService._delta_pct(current["revenue"], previous["revenue"]),
            },
            "average_ticket": {
                "value": current["average_ticket"],
                "previous": previous["average_ticket"],
                "delta_pct": DashboardService._delta_pct(
                    current["average_ticket"], previous["average_ticket"]
                ),
            },
            "cancelled": {
                "value": current["cancelled_orders"],
                "previous": previous["cancelled_orders"],
                "delta_pct": DashboardService._delta_pct(
                    current["cancelled_orders"], previous["cancelled_orders"]
                ),
            },
            "cancellation_rate": {
                "value": cur_rate,
                "previous": prev_rate,
                "delta_pct": DashboardService._delta_pct(cur_rate, prev_rate),
            },
        }

    @staticmethod
    def _completed_qs(company: Company, start: datetime, end: datetime):
        return DashboardService._orders_qs(company, start, end).filter(
            status=OrderStatus.COMPLETED
        )

    @staticmethod
    def _series_hourly(company: Company, day: date) -> list[dict]:
        start, end = DashboardService._day_bounds(company, day)
        tz = DashboardService._tz(company)
        rows = (
            DashboardService._completed_qs(company, start, end)
            .annotate(bucket=TruncHour("created_at", tzinfo=tz))
            .values("bucket")
            .annotate(
                orders=Count("id"),
                revenue=Sum("total"),
            )
            .order_by("bucket")
        )
        by_hour = {
            row["bucket"].astimezone(tz).hour: row for row in rows if row["bucket"] is not None
        }
        points = []
        for hour in range(24):
            row = by_hour.get(hour)
            orders = row["orders"] if row else 0
            revenue = float(row["revenue"] or 0) if row else 0.0
            ticket = round(revenue / orders, 2) if orders else 0.0
            points.append(
                {
                    "label": f"{hour:02d}:00",
                    "orders": orders,
                    "revenue": revenue,
                    "average_ticket": ticket,
                }
            )
        return points

    @staticmethod
    def _series_daily(company: Company, start_day: date, end_day: date) -> list[dict]:
        start, end = DashboardService._range_bounds(company, start_day, end_day)
        tz = DashboardService._tz(company)
        rows = (
            DashboardService._completed_qs(company, start, end)
            .annotate(bucket=TruncDate("created_at", tzinfo=tz))
            .values("bucket")
            .annotate(orders=Count("id"), revenue=Sum("total"))
            .order_by("bucket")
        )
        by_day = {row["bucket"]: row for row in rows if row["bucket"] is not None}
        points = []
        cursor = start_day
        while cursor <= end_day:
            row = by_day.get(cursor)
            orders = row["orders"] if row else 0
            revenue = float(row["revenue"] or 0) if row else 0.0
            ticket = round(revenue / orders, 2) if orders else 0.0
            points.append(
                {
                    "label": cursor.strftime("%d/%m"),
                    "orders": orders,
                    "revenue": revenue,
                    "average_ticket": ticket,
                }
            )
            cursor += timedelta(days=1)
        return points

    @staticmethod
    def _by_hour(company: Company, start_day: date, end_day: date) -> dict:
        start, end = DashboardService._range_bounds(company, start_day, end_day)
        tz = DashboardService._tz(company)
        rows = (
            DashboardService._completed_qs(company, start, end)
            .annotate(bucket=TruncHour("created_at", tzinfo=tz))
            .values("bucket")
            .annotate(orders=Count("id"))
        )

        weekday_slots = {f"{a}-{b}": 0 for a, b in HOUR_SLOTS}
        weekend_slots = {f"{a}-{b}": 0 for a, b in HOUR_SLOTS}

        for row in rows:
            bucket = row["bucket"]
            if bucket is None:
                continue
            local = bucket.astimezone(tz)
            slot_start = (local.hour // 2) * 2
            key = f"{slot_start}-{slot_start + 2}"
            target = weekend_slots if local.weekday() >= 5 else weekday_slots
            if key in target:
                target[key] += row["orders"] or 0

        def to_list(slots: dict) -> list[dict]:
            return [{"slot": k, "orders": v} for k, v in slots.items()]

        weekday_list = to_list(weekday_slots)
        weekend_list = to_list(weekend_slots)
        combined = {
            s["slot"]: weekday_slots[s["slot"]] + weekend_slots[s["slot"]] for s in weekday_list
        }
        peak_slot = max(combined, key=combined.get) if combined else "18-20"
        peak_orders = combined.get(peak_slot, 0)

        return {
            "weekday": weekday_list,
            "weekend": weekend_list,
            "peak_slot": peak_slot,
            "peak_orders": peak_orders,
        }

    @staticmethod
    def _by_weekday(company: Company, start_day: date, end_day: date) -> dict:
        start, end = DashboardService._range_bounds(company, start_day, end_day)
        tz = DashboardService._tz(company)
        rows = (
            DashboardService._completed_qs(company, start, end)
            .annotate(bucket=TruncDate("created_at", tzinfo=tz))
            .values("bucket")
            .annotate(orders=Count("id"))
        )
        totals = [0] * 7
        for row in rows:
            bucket = row["bucket"]
            if bucket is None:
                continue
            totals[bucket.weekday()] += row["orders"] or 0

        days = [
            {"weekday": i, "label": WEEKDAY_LABELS[i], "orders": totals[i]} for i in range(7)
        ]
        best_weekday = max(range(7), key=lambda i: totals[i]) if any(totals) else 0
        return {
            "days": days,
            "best_weekday": best_weekday,
            "best_orders": totals[best_weekday],
        }

    @staticmethod
    def _by_payment(company: Company, start_day: date, end_day: date) -> list[dict]:
        start, end = DashboardService._range_bounds(company, start_day, end_day)
        rows = (
            OrderPayment.all_objects.filter(
                order__tenant=company,
                order__status=OrderStatus.COMPLETED,
                order__created_at__gte=start,
                order__created_at__lte=end,
            )
            .values("method")
            .annotate(orders=Count("id"))
            .order_by("-orders")
        )
        result = []
        for row in rows:
            method = row["method"]
            count = row["orders"] or 0
            if count <= 0:
                continue
            result.append(
                {
                    "method": method,
                    "label": PAYMENT_LABELS.get(method, method),
                    "orders": count,
                }
            )
        return result

    @staticmethod
    def _top_products(company: Company, start_day: date, end_day: date, *, limit: int = 5) -> list[dict]:
        start, end = DashboardService._range_bounds(company, start_day, end_day)
        rows = (
            OrderItem.all_objects.filter(
                order__tenant=company,
                order__status=OrderStatus.COMPLETED,
                order__created_at__gte=start,
                order__created_at__lte=end,
            )
            .values("product_id", "product_name")
            .annotate(
                quantity=Sum("quantity"),
                revenue=Sum("total_price"),
                orders=Count("order_id", distinct=True),
            )
            .order_by("-quantity", "-revenue")[:limit]
        )
        return [
            {
                "product_id": str(row["product_id"]) if row["product_id"] else None,
                "name": row["product_name"],
                "quantity": int(row["quantity"] or 0),
                "revenue": float(row["revenue"] or 0),
                "orders": int(row["orders"] or 0),
            }
            for row in rows
        ]

    @staticmethod
    def _slow_products(company: Company, start_day: date, end_day: date, *, limit: int = 5) -> list[dict]:
        # produtos ativos com pouca (ou zero) venda no período
        start, end = DashboardService._range_bounds(company, start_day, end_day)
        sold = {
            str(row["product_id"]): int(row["quantity"] or 0)
            for row in OrderItem.all_objects.filter(
                order__tenant=company,
                order__status=OrderStatus.COMPLETED,
                order__created_at__gte=start,
                order__created_at__lte=end,
                product_id__isnull=False,
            )
            .values("product_id")
            .annotate(quantity=Sum("quantity"))
        }
        products = list(
            Product.all_objects.filter(
                tenant=company,
                is_available=True,
                deleted_at__isnull=True,
            ).order_by("name")[:80]
        )
        ranked = []
        for p in products:
            qty = sold.get(str(p.id), 0)
            ranked.append(
                {
                    "product_id": str(p.id),
                    "name": p.name,
                    "quantity": qty,
                    "revenue": 0.0,
                    "orders": 0,
                }
            )
        ranked.sort(key=lambda x: (x["quantity"], x["name"]))
        # só mostra se tem pelo menos um com venda baixa relativa ao top
        return ranked[:limit]

    @staticmethod
    def _by_delivery(company: Company, start_day: date, end_day: date) -> dict:
        start, end = DashboardService._range_bounds(company, start_day, end_day)
        rows = (
            DashboardService._completed_qs(company, start, end)
            .values("delivery_type")
            .annotate(orders=Count("id"))
            .order_by("-orders")
        )
        items = []
        total = 0
        for row in rows:
            count = int(row["orders"] or 0)
            if count <= 0:
                continue
            total += count
            method = row["delivery_type"]
            items.append(
                {
                    "method": method,
                    "label": DELIVERY_LABELS.get(method, method),
                    "orders": count,
                }
            )
        for item in items:
            item["pct"] = round((item["orders"] / total) * 100, 1) if total else 0.0
        return {"total": total, "items": items}

    @staticmethod
    def _customer_split(company: Company, start_day: date, end_day: date) -> dict:
        # novo = 1ª compra concluída cai no período; recorrente = já comprou antes
        start, end = DashboardService._range_bounds(company, start_day, end_day)
        period_customers = (
            DashboardService._completed_qs(company, start, end)
            .exclude(customer_id=None)
            .order_by("customer_id")
            .values_list("customer_id", flat=True)
            .distinct()
        )
        customer_ids = list(period_customers)
        if not customer_ids:
            return {
                "new": 0,
                "returning": 0,
                "total": 0,
                "new_pct": 0.0,
                "returning_pct": 0.0,
            }

        prior = set(
            Order.all_objects.filter(
                tenant=company,
                status=OrderStatus.COMPLETED,
                created_at__lt=start,
                customer_id__in=customer_ids,
            )
            .order_by("customer_id")
            .values_list("customer_id", flat=True)
            .distinct()
        )
        returning = sum(1 for cid in customer_ids if cid in prior)
        new = len(customer_ids) - returning
        total = len(customer_ids)
        return {
            "new": new,
            "returning": returning,
            "total": total,
            "new_pct": round((new / total) * 100, 1) if total else 0.0,
            "returning_pct": round((returning / total) * 100, 1) if total else 0.0,
        }

    @staticmethod
    def _recent_orders(company: Company) -> list[dict]:
        # fila ao vivo do dia — independente do chip
        today = DashboardService._tenant_today(company)
        start, end = DashboardService._day_bounds(company, today)
        recent = (
            Order.all_objects.filter(
                tenant=company,
                created_at__gte=start,
                created_at__lte=end,
            )
            .select_related("customer")
            .order_by("-created_at")[:8]
            .values(
                "id",
                "order_number",
                "status",
                "customer_name",
                "total",
                "created_at",
            )
        )
        return [
            {
                "id": str(row["id"]),
                "order_number": row["order_number"],
                "status": row["status"],
                "customer_name": row["customer_name"],
                "total": float(row["total"]),
                "created_at": row["created_at"].isoformat().replace("+00:00", "Z"),
            }
            for row in recent
        ]

    @classmethod
    def get_dashboard(
        cls,
        company: Company,
        period: str = PERIOD_TODAY,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict:
        if period not in VALID_PERIODS:
            period = PERIOD_TODAY

        cur_start, cur_end, prev_start, prev_end, compare_label = cls._period_windows(
            company, period, from_date=from_date, to_date=to_date
        )
        cur_bounds = cls._range_bounds(company, cur_start, cur_end)
        prev_bounds = cls._range_bounds(company, prev_start, prev_end)

        current_summary = cls._range_summary(
            company, cur_bounds[0], cur_bounds[1], cur_end.isoformat()
        )
        previous_summary = cls._range_summary(
            company, prev_bounds[0], prev_bounds[1], prev_end.isoformat()
        )

        today = cls._tenant_today(company)
        today_summary = cls._day_summary(company, today)
        yesterday_summary = cls._day_summary(company, today - timedelta(days=1))

        # um dia só → série por hora; vários dias → por dia
        if cur_start == cur_end:
            granularity = "hour"
            series_current = cls._series_hourly(company, cur_start)
            series_previous = cls._series_hourly(company, prev_start)
        else:
            granularity = "day"
            series_current = cls._series_daily(company, cur_start, cur_end)
            series_previous = cls._series_daily(company, prev_start, prev_end)

        return {
            "period": period,
            "compare_period": {
                "label": compare_label,
                "start": prev_start.isoformat(),
                "end": prev_end.isoformat(),
            },
            "period_range": {
                "start": cur_start.isoformat(),
                "end": cur_end.isoformat(),
            },
            "kpis": cls._build_kpis(current_summary, previous_summary),
            "operational": {
                "pending_orders": today_summary["pending_orders"],
                "preparing_orders": today_summary["preparing_orders"],
                "completed_orders": today_summary["completed_orders"],
            },
            "series": {
                "granularity": granularity,
                "metric_keys": ["orders", "revenue", "average_ticket"],
                "current": series_current,
                "previous": series_previous,
            },
            "by_hour": cls._by_hour(company, cur_start, cur_end),
            "by_weekday": cls._by_weekday(company, cur_start, cur_end),
            "by_payment_method": cls._by_payment(company, cur_start, cur_end),
            "top_products": cls._top_products(company, cur_start, cur_end),
            "slow_products": cls._slow_products(company, cur_start, cur_end),
            "by_delivery_type": cls._by_delivery(company, cur_start, cur_end),
            "customers": cls._customer_split(company, cur_start, cur_end),
            "recent_orders": cls._recent_orders(company),
            # compat MVP até o front migrar 100%
            "today": today_summary,
            "yesterday": {
                "date": yesterday_summary["date"],
                "total_orders": yesterday_summary["total_orders"],
                "revenue": yesterday_summary["revenue"],
            },
        }
