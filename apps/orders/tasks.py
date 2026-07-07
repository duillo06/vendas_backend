import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from apps.orders.models import Order

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_order_confirmation_email(self, order_id: str) -> None:
    try:
        order = (
            Order.all_objects.select_related("customer", "tenant")
            .prefetch_related("items__options")
            .get(id=order_id)
        )
    except Order.DoesNotExist:
        logger.warning("Pedido %s não encontrado para envio de e-mail", order_id)
        return

    recipient = (order.customer.email or "").strip()
    if not recipient:
        logger.info("Pedido %s sem e-mail do cliente — confirmação não enviada", order.order_number)
        return

    storefront_url = _build_tracking_url(order)
    context = {
        "order": order,
        "company": order.tenant,
        "items": list(order.items.all()),
        "tracking_url": storefront_url,
    }

    subject = f"Pedido {order.order_number} recebido — {order.tenant.trade_name}"
    message = render_to_string("orders/emails/order_confirmation.txt", context)

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        fail_silently=False,
    )


def _build_tracking_url(order: Order) -> str:
    base_domain = getattr(settings, "STOREFRONT_BASE_DOMAIN", "foodservice.app")
    subdomain = order.tenant.subdomain
    return f"https://{subdomain}.{base_domain}/pedido/{order.id}"
