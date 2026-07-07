from django.urls import path

from apps.accounts.views.auth_views import MeView

urlpatterns = [
    path("me/", MeView.as_view(), name="admin-me"),
]
