from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import EmployeeJWTAuthentication
from apps.accounts.permissions import IsEmployeeAuthenticated
from apps.companies.services.company_admin_service import CompanyAdminService
from apps.companies.services.first_setup_service import FirstSetupError, FirstSetupService
from apps.companies.services.logo_service import CompanyLogoService
from apps.orders.services.dashboard_service import DashboardService
from core.permissions.rbac import HasPermission


class AdminSettingsView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        if not HasPermission("settings.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        company = request.user.employee.tenant
        return Response(CompanyAdminService.get_settings_payload(company))

    def patch(self, request):
        if not HasPermission("settings.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        company = request.user.employee.tenant
        try:
            payload = CompanyAdminService.update_settings(company, request.data)
        except DjangoValidationError as exc:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(payload)


class AdminLogoUploadView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if not HasPermission("settings.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        image_file = request.FILES.get("logo") or request.FILES.get("file")
        if image_file is None:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "Arquivo de logo é obrigatório"}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        company = request.user.employee.tenant
        try:
            logo_url = CompanyLogoService.upload(company=company, image_file=image_file)
        except DjangoValidationError as exc:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        from core.utils.media import absolutize_media_url

        return Response({"logo_url": absolutize_media_url(logo_url, request)})


class AdminCoverUploadView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if not HasPermission("settings.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        image_file = request.FILES.get("cover") or request.FILES.get("file")
        if image_file is None:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "Arquivo de capa é obrigatório"}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        company = request.user.employee.tenant
        try:
            cover_url = CompanyLogoService.upload_cover(company=company, image_file=image_file)
        except DjangoValidationError as exc:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        from core.utils.media import absolutize_media_url

        return Response({"cover_url": absolutize_media_url(cover_url, request)})


class AdminDashboardView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get(self, request):
        if not HasPermission("dashboard.view").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        company = request.user.employee.tenant
        return Response(DashboardService.get_dashboard(company))


class AdminSetupView(APIView):
    """Estado e segmentos do assistente de 1ª configuração."""

    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get(self, request):
        if not (
            HasPermission("settings.manage").has_permission(request, self)
            or HasPermission("catalog.manage").has_permission(request, self)
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        company = request.user.employee.tenant
        return Response(
            {
                "setup": FirstSetupService.get(company),
                "segments": FirstSetupService.list_segments(),
            }
        )


class AdminSetupApplyView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def post(self, request):
        if not HasPermission("catalog.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        segment = request.data.get("segment")
        if not segment:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "Escolha o que você vende"}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        company = request.user.employee.tenant
        try:
            result = FirstSetupService.apply_segment(company, str(segment))
        except FirstSetupError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return Response(result)


class AdminSetupDismissView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def post(self, request):
        if not (
            HasPermission("settings.manage").has_permission(request, self)
            or HasPermission("catalog.manage").has_permission(request, self)
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        company = request.user.employee.tenant
        return Response({"setup": FirstSetupService.dismiss(company)})


class AdminAiSuggestionsStubView(APIView):
    """Hook futuro de IA — stub da Fase 4 (sem modelo)."""

    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get(self, request):
        return Response(
            {
                "available": False,
                "suggestions": [],
                "message": "Sugestões inteligentes chegam em breve.",
            }
        )

    def post(self, request):
        return self.get(request)
