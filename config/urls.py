from django.urls import include, path

from core.views.health import HealthCheckView

urlpatterns = [
    path("api/v1/health/", HealthCheckView.as_view(), name="health-check"),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/admin/", include("apps.admin_urls")),
]
