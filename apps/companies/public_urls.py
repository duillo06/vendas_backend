from django.urls import path

from apps.companies.views.public_views import PublicCompanyView

urlpatterns = [
    path("", PublicCompanyView.as_view(), name="public-company"),
]
