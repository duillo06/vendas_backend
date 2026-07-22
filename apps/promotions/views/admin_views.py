from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import EmployeeJWTAuthentication
from apps.accounts.permissions import IsEmployeeAuthenticated
from apps.promotions.models import Campaign
from apps.promotions.serializers import CampaignAdminSerializer, CampaignWriteSerializer
from apps.promotions.services.campaign_service import CampaignService
from apps.promotions.domain.exceptions import InvalidCampaignError
from core.permissions.rbac import HasPermission


class AdminCampaignViewSet(viewsets.ViewSet):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get_tenant(self):
        return self.request.user.employee.tenant

    def list(self, request):
        if not HasPermission("promotions.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        qs = (
            Campaign.all_objects.filter(tenant=self.get_tenant())
            .select_related("product")
            .order_by("-created_at")
        )
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(CampaignAdminSerializer(qs, many=True).data)

    def create(self, request):
        if not HasPermission("promotions.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = CampaignWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            campaign = CampaignService.create(
                tenant=self.get_tenant(),
                data=serializer.validated_data,
            )
        except InvalidCampaignError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        campaign = Campaign.all_objects.select_related("product").get(pk=campaign.pk)
        return Response(
            CampaignAdminSerializer(campaign).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, pk=None):
        if not HasPermission("promotions.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        campaign = Campaign.all_objects.select_related("product").get(
            pk=pk,
            tenant=self.get_tenant(),
        )
        return Response(CampaignAdminSerializer(campaign).data)

    def partial_update(self, request, pk=None):
        if not HasPermission("promotions.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        campaign = Campaign.all_objects.select_related("product").get(
            pk=pk,
            tenant=self.get_tenant(),
        )
        serializer = CampaignWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            campaign = CampaignService.update(campaign=campaign, data=serializer.validated_data)
        except InvalidCampaignError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        campaign = Campaign.all_objects.select_related("product").get(pk=campaign.pk)
        return Response(CampaignAdminSerializer(campaign).data)
