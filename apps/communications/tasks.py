import logging
import time

from celery import shared_task
from django.utils import timezone

from apps.communications.domain.catalog import human_error
from apps.communications.domain.enums import ConnectionStatus, DispatchStatus
from apps.communications.infrastructure.providers.evolution.client import EvolutionHttpError
from apps.communications.infrastructure.providers.registry import get_provider
from apps.communications.models import CommunicationConnection, MessageDispatch
from apps.communications.services.connection_service import ConnectionService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_dispatch(self, dispatch_id: str) -> None:
    try:
        dispatch = MessageDispatch.all_objects.select_related("connection", "tenant").get(
            id=dispatch_id,
        )
    except MessageDispatch.DoesNotExist:
        logger.warning("dispatch %s não encontrado", dispatch_id)
        return

    if dispatch.status in (DispatchStatus.SENT, DispatchStatus.DELIVERED):
        return

    connection = dispatch.connection
    if not connection or connection.status != ConnectionStatus.CONNECTED:
        dispatch.status = DispatchStatus.FAILED
        dispatch.error_code = "session_disconnected"
        dispatch.error_message = human_error("session_disconnected")
        dispatch.save(
            update_fields=["status", "error_code", "error_message", "updated_at"],
        )
        return

    provider = get_provider(connection.provider_key)
    ctx = ConnectionService.build_ctx(connection)
    started = time.monotonic()
    try:
        result = provider.send_text(
            ctx,
            to_e164=dispatch.recipient,
            body=dispatch.body_snapshot,
        )
    except EvolutionHttpError as exc:
        if self.request.retries < self.max_retries and exc.error_code in (
            "provider_timeout",
            "server_unreachable",
        ):
            raise self.retry(exc=exc) from exc
        dispatch.status = DispatchStatus.FAILED
        dispatch.error_code = exc.error_code
        dispatch.error_message = human_error(exc.error_code)
        dispatch.save(
            update_fields=["status", "error_code", "error_message", "updated_at"],
        )
        return
    except Exception as exc:
        logger.exception("erro ao enviar dispatch %s", dispatch_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc) from exc
        dispatch.status = DispatchStatus.FAILED
        dispatch.error_code = "send_failed"
        dispatch.error_message = human_error("send_failed")
        dispatch.save(
            update_fields=["status", "error_code", "error_message", "updated_at"],
        )
        return

    dispatch.status = DispatchStatus.SENT
    dispatch.provider_message_id = result.provider_message_id or ""
    dispatch.sent_at = timezone.now()
    dispatch.latency_ms = int((time.monotonic() - started) * 1000)
    dispatch.save(
        update_fields=[
            "status",
            "provider_message_id",
            "sent_at",
            "latency_ms",
            "updated_at",
        ],
    )


@shared_task
def run_connection_health(connection_id: str) -> None:
    try:
        connection = CommunicationConnection.all_objects.get(id=connection_id)
    except CommunicationConnection.DoesNotExist:
        return
    ConnectionService.run_health_check(connection=connection)


@shared_task
def run_all_connections_health() -> None:
    qs = CommunicationConnection.all_objects.exclude(
        status=ConnectionStatus.PENDING,
    )
    for connection in qs.iterator():
        try:
            ConnectionService.run_health_check(connection=connection)
        except Exception:
            logger.exception("health falhou p/ connection %s", connection.id)
