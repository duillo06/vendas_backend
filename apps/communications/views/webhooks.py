import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView

from apps.communications.infrastructure.providers.registry import get_provider
from apps.communications.models import CommunicationConnection
from apps.communications.services.connection_service import ConnectionService

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class CommunicationsWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, provider_key: str):
        try:
            provider = get_provider(provider_key)
        except KeyError:
            return HttpResponse(status=404)

        events = provider.parse_webhook(dict(request.headers), request.body)
        if not events:
            return HttpResponse(status=200)

        # tenta achar a conexão pelo instance name no body
        instance_name = _extract_instance(request.data if hasattr(request, "data") else {})
        qs = CommunicationConnection.all_objects.filter(provider_key=provider_key)
        if instance_name:
            matched = None
            for conn in qs.iterator():
                meta = conn.provider_metadata or {}
                if meta.get("instance_name") == instance_name:
                    matched = conn
                    break
            if matched:
                ConnectionService.apply_webhook_events(connection=matched, events=events)
                return HttpResponse(status=200)

        # fallback: aplica em conexões awaiting_qr / connected do provider
        for conn in qs.filter(status__in=["awaiting_qr", "connected", "disconnected"])[:20]:
            try:
                ConnectionService.apply_webhook_events(connection=conn, events=events)
            except Exception:
                logger.exception("webhook apply falhou p/ %s", conn.id)

        return HttpResponse(status=200)


def _extract_instance(data) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in ("instance", "instanceName", "instance_name"):
        val = data.get(key)
        if isinstance(val, str) and val:
            return val
        if isinstance(val, dict):
            name = val.get("instanceName") or val.get("name")
            if name:
                return str(name)
    return None
