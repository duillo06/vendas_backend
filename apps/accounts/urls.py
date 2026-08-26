from django.urls import path

from apps.accounts.views.auth_views import (
    ChangePasswordView,
    LoginView,
    LogoutView,
    MeView,
    RefreshView,
)
from apps.accounts.views.customer_auth_views import (
    CustomerLoginView,
    CustomerLogoutView,
    CustomerRefreshView,
    CustomerRegisterView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("customer/register/", CustomerRegisterView.as_view(), name="customer-register"),
    path("customer/login/", CustomerLoginView.as_view(), name="customer-login"),
    path("customer/refresh/", CustomerRefreshView.as_view(), name="customer-refresh"),
    path("customer/logout/", CustomerLogoutView.as_view(), name="customer-logout"),
]
