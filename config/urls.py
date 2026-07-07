from django.urls import path

from core.views.health import HealthCheckView

urlpatterns = [
    path("api/v1/health/", HealthCheckView.as_view(), name="health-check"),
]
