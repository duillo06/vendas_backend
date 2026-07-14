from __future__ import annotations

import zoneinfo
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.companies.models import Company
from apps.orders.domain.enums import OrderStatus
from apps.orders.models import Order


class DashboardService:
    @staticmethod
    def _tenant_today(company: Company):
        tz = zoneinfo.ZoneInfo(company.timezone)
        return timezone.now().astimezone(tz).date()

    @staticmethod
    def _day_bounds(company: Company, day) -> tuple[datetime, datetime]:
        tz = zoneinfo.ZoneInfo(company.timezone)
        start = datetime.combine(day, time.min, tzinfo=tz)
        end = datetime.combine(day, time.max, tzinfo=tz)
        return start, end

    @staticmethod
    def _day_summary(company: Company, day) -> dict:
        # agregado do dia no fuso da loja
        start, end = DashboardService._day_bounds(company, day)
        qs = Order.all_objects.filter(
            tenant=company,
            created_at__gte=start,
            created_at__lte=end,
        )
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
            "date": day.isoformat(),
            "total_orders": total_orders,
            "pending_orders": counts["pending_orders"] or 0,
            "preparing_orders": counts["preparing_orders"] or 0,
            "completed_orders": completed_orders,
            "cancelled_orders": counts["cancelled_orders"] or 0,
            "revenue": float(revenue),
            "average_ticket": round(average_ticket, 2),
        }

    @staticmethod
    def get_dashboard(company: Company) -> dict:
        today = DashboardService._tenant_today(company)
        yesterday = today - timedelta(days=1)
        today_summary = DashboardService._day_summary(company, today)
        yesterday_summary = DashboardService._day_summary(company, yesterday)

        start, end = DashboardService._day_bounds(company, today)
        recent_orders = (
            Order.all_objects.filter(
                tenant=company,
                created_at__gte=start,
                created_at__lte=end,
            )
            .select_related("customer")
            .order_by("-created_at")[:5]
            .values(
                "id",
                "order_number",
                "status",
                "customer_name",
                "total",
                "created_at",
            )
        )

        return {
            "today": today_summary,
            "yesterday": {
                "date": yesterday_summary["date"],
                "total_orders": yesterday_summary["total_orders"],
                "revenue": yesterday_summary["revenue"],
            },
            "recent_orders": [
                {
                    "id": str(row["id"]),
                    "order_number": row["order_number"],
                    "status": row["status"],
                    "customer_name": row["customer_name"],
                    "total": float(row["total"]),
                    "created_at": row["created_at"].isoformat().replace("+00:00", "Z"),
                }
                for row in recent_orders
            ],
        }
