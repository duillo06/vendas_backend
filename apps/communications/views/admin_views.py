from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import EmployeeJWTAuthentication
from apps.accounts.permissions import IsEmployeeAuthenticated
from apps.communications.domain.catalog import SITUATION_CATALOG, human_error
from apps.communications.domain.enums import ConnectionStatus, DispatchStatus
from apps.communications.domain.exceptions import (
    CommunicationError,
    TemplateValidationError,
)
from apps.communications.models import MessageDispatch, MerchantAlert
from apps.communications.serializers import (
    ConnectionTestSerializer,
    ConnectWhatsAppSerializer,
    SituationBulkSerializer,
    TemplatePreviewSerializer,
    TemplateTestSerializer,
    TemplateWriteSerializer,
)
from apps.communications.services.connection_service import ConnectionService
from apps.communications.services.engine import CommunicationEngine
from apps.communications.services.template_service import TemplateService
from core.permissions.rbac import HasPermission


def _forbid(request, view):
    if not HasPermission("connections.manage").has_permission(request, view):
        return Response(status=status.HTTP_403_FORBIDDEN)
    return None


def _serialize_connection(connection) -> dict:
    if connection is None:
        return {
            "connected": False,
            "status": "none",
            "phone_display": "",
            "provider_key": "evolution",
            "connection_mode": None,
            "last_health": None,
        }
    meta = connection.provider_metadata or {}
    return {
        "id": str(connection.id),
        "connected": connection.status == ConnectionStatus.CONNECTED,
        "status": connection.status,
        "phone_display": connection.phone_display,
        "phone_e164": connection.phone_e164,
        "provider_key": connection.provider_key,
        "connection_mode": meta.get("connection_mode"),
        "last_health_at": connection.last_health_at,
        "last_health": connection.last_health_status or None,
        "last_error_code": connection.last_error_code,
        "last_error_message": human_error(connection.last_error_code)
        if connection.last_error_code
        else "",
    }


class WhatsAppOptionsView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get(self, request):
        if err := _forbid(request, self):
            return err
        return Response(ConnectionService.connection_options())


class WhatsAppStatusView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get(self, request):
        if err := _forbid(request, self):
            return err
        tenant = request.user.employee.tenant
        connection = ConnectionService.get_whatsapp(tenant=tenant)
        return Response(_serialize_connection(connection))


class WhatsAppConnectView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def post(self, request):
        if err := _forbid(request, self):
            return err
        serializer = ConnectWhatsAppSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            connection = ConnectionService.start_whatsapp_connection(
                tenant=request.user.employee.tenant,
                mode=serializer.validated_data.get("mode") or ConnectionService.MODE_BYO,
                base_url=serializer.validated_data.get("base_url") or "",
                api_key=serializer.validated_data.get("api_key") or "",
                provider_key=serializer.validated_data.get("provider_key")
                or "evolution",
            )
        except CommunicationError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return Response(_serialize_connection(connection), status=status.HTTP_201_CREATED)


class WhatsAppQrView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get(self, request):
        if err := _forbid(request, self):
            return err
        connection = ConnectionService.get_whatsapp(tenant=request.user.employee.tenant)
        if not connection:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Nenhuma conexão em andamento."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            data = ConnectionService.get_qr(connection=connection)
        except CommunicationError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        connection.refresh_from_db()
        return Response({**data, "connection": _serialize_connection(connection)})


class WhatsAppHealthView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def post(self, request):
        if err := _forbid(request, self):
            return err
        connection = ConnectionService.get_whatsapp(tenant=request.user.employee.tenant)
        if not connection:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Conecte o WhatsApp primeiro."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        snap = ConnectionService.run_health_check(connection=connection)
        connection.refresh_from_db()
        return Response(
            {
                "ok": snap.ok,
                "steps": snap.steps,
                "checked_at": snap.checked_at,
                "connection": _serialize_connection(connection),
            },
        )


class WhatsAppDisconnectView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def post(self, request):
        if err := _forbid(request, self):
            return err
        connection = ConnectionService.get_whatsapp(tenant=request.user.employee.tenant)
        if not connection:
            return Response(status=status.HTTP_404_NOT_FOUND)
        connection = ConnectionService.disconnect(connection=connection)
        return Response(_serialize_connection(connection))


class WhatsAppConnectionTestView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def post(self, request):
        if err := _forbid(request, self):
            return err
        connection = ConnectionService.get_whatsapp(tenant=request.user.employee.tenant)
        if not connection or connection.status != ConnectionStatus.CONNECTED:
            return Response(
                {
                    "error": {
                        "code": "NOT_CONNECTED",
                        "message": "Conecte o WhatsApp antes de enviar o teste.",
                    },
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        serializer = ConnectionTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            dispatch = CommunicationEngine.send_test(
                connection=connection,
                body=serializer.validated_data.get("message")
                or "Olá! 🎉 Seu WhatsApp foi conectado com sucesso ao sistema.",
            )
        except ValueError as exc:
            return Response(
                {"error": {"code": "SEND_FAILED", "message": str(exc)}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return Response(
            {
                "ok": dispatch.status == DispatchStatus.SENT,
                "status": dispatch.status,
                "message": "Mensagem de teste enviada — confira no celular."
                if dispatch.status == DispatchStatus.SENT
                else dispatch.error_message,
            },
        )


class SituationListView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get(self, request):
        if err := _forbid(request, self):
            return err
        return Response(TemplateService.list_situations(tenant=request.user.employee.tenant))


class SituationBulkView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def post(self, request):
        if err := _forbid(request, self):
            return err
        serializer = SituationBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        TemplateService.bulk_set_enabled(
            tenant=request.user.employee.tenant,
            enabled_map=serializer.validated_data["situations"],
        )
        return Response(TemplateService.list_situations(tenant=request.user.employee.tenant))


class TemplateDetailView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get(self, request, event_key: str):
        if err := _forbid(request, self):
            return err
        try:
            tpl = TemplateService.get_template(
                tenant=request.user.employee.tenant,
                event_key=event_key,
            )
        except TemplateValidationError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message}},
                status=status.HTTP_404_NOT_FOUND,
            )
        meta = SITUATION_CATALOG[event_key]
        return Response(
            {
                "event_key": event_key,
                "title": meta["title"],
                "description": meta["description"],
                "variables": meta["variables"],
                "body": tpl.body,
            },
        )

    def put(self, request, event_key: str):
        if err := _forbid(request, self):
            return err
        serializer = TemplateWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tpl = TemplateService.save_template(
                tenant=request.user.employee.tenant,
                event_key=event_key,
                body=serializer.validated_data["body"],
            )
        except TemplateValidationError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        meta = SITUATION_CATALOG[event_key]
        return Response(
            {
                "event_key": event_key,
                "title": meta["title"],
                "variables": meta["variables"],
                "body": tpl.body,
            },
        )


class TemplatePreviewView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def post(self, request, event_key: str):
        if err := _forbid(request, self):
            return err
        serializer = TemplatePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = request.user.employee.tenant
        body = serializer.validated_data.get("body")
        if not body:
            tpl = TemplateService.get_template(tenant=tenant, event_key=event_key)
            body = tpl.body
        preview = CommunicationEngine.preview(
            body=body,
            company_name=tenant.trade_name,
        )
        return Response({"preview": preview})


class TemplateTestView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def post(self, request, event_key: str):
        if err := _forbid(request, self):
            return err
        connection = ConnectionService.get_whatsapp(tenant=request.user.employee.tenant)
        if not connection or connection.status != ConnectionStatus.CONNECTED:
            return Response(
                {
                    "error": {
                        "code": "NOT_CONNECTED",
                        "message": "Conecte o WhatsApp antes de enviar o teste.",
                    },
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        serializer = TemplateTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data.get("body")
        if not body:
            body = TemplateService.get_template(
                tenant=request.user.employee.tenant,
                event_key=event_key,
            ).body
        rendered = CommunicationEngine.preview(
            body=body,
            company_name=request.user.employee.tenant.trade_name,
        )
        try:
            dispatch = CommunicationEngine.send_test(connection=connection, body=rendered)
        except ValueError as exc:
            return Response(
                {"error": {"code": "SEND_FAILED", "message": str(exc)}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return Response({"ok": True, "status": dispatch.status})


class WhatsAppStatsView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get(self, request):
        if err := _forbid(request, self):
            return err
        tenant = request.user.employee.tenant
        start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        qs = MessageDispatch.all_objects.filter(
            tenant=tenant,
            created_at__gte=start,
            is_test=False,
        )
        agg = qs.aggregate(
            sent=Count("id", filter=Q(status__in=[DispatchStatus.SENT, DispatchStatus.DELIVERED])),
            delivered=Count("id", filter=Q(status=DispatchStatus.DELIVERED)),
            failed=Count("id", filter=Q(status=DispatchStatus.FAILED)),
            pending=Count(
                "id",
                filter=Q(status__in=[DispatchStatus.PENDING, DispatchStatus.QUEUED]),
            ),
            avg_latency=Avg("latency_ms"),
        )
        last = (
            qs.filter(status__in=[DispatchStatus.SENT, DispatchStatus.DELIVERED])
            .order_by("-sent_at")
            .first()
        )
        return Response(
            {
                "today": {
                    "sent": agg["sent"] or 0,
                    "delivered": agg["delivered"] or 0,
                    "failed": agg["failed"] or 0,
                    "pending": agg["pending"] or 0,
                    "avg_latency_ms": int(agg["avg_latency"] or 0),
                    "last_sent_at": last.sent_at if last else None,
                },
            },
        )


class AlertsListView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get(self, request):
        if err := _forbid(request, self):
            return err
        qs = MerchantAlert.all_objects.filter(
            tenant=request.user.employee.tenant,
            resolved_at__isnull=True,
        ).order_by("-created_at")[:20]
        return Response(
            [
                {
                    "id": str(a.id),
                    "kind": a.kind,
                    "severity": a.severity,
                    "title": a.title,
                    "body": a.body,
                    "action_hint": a.action_hint,
                    "created_at": a.created_at,
                }
                for a in qs
            ],
        )
