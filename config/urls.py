from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from core.views.health import HealthCheckView

urlpatterns = [
    path("api/v1/health/", HealthCheckView.as_view(), name="health-check"),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/public/", include("apps.public_urls")),
    path("api/v1/admin/", include("apps.admin_urls")),
]

# Em dev o runserver precisa servir uploads; em prod o Nginx cobre /media/
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
