from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("refresh/", views.CookieTokenRefreshView.as_view(), name="auth-refresh"),
    path("csrf/", views.CSRFTokenView.as_view(), name="auth-csrf"),
    path("me/", views.MeView.as_view(), name="auth-me"),
    path("change-password/", views.ChangePasswordView.as_view(), name="change-password"),
    path("users/", views.UserListView.as_view(), name="user-list"),
    path("users/<uuid:pk>/", views.UserDetailView.as_view(), name="user-detail"),
    path("users/<uuid:pk>/toggle-active/", views.DeactivateUserView.as_view(), name="user-toggle-active"),
    path("users/<uuid:pk>/reset-password/", views.AdminPasswordResetView.as_view(), name="user-reset-password"),
    path("nca-divisions/", views.NCADivisionListCreateView.as_view(), name="nca-division-list"),
    path("nca-divisions/<int:pk>/", views.NCADivisionDetailView.as_view(), name="nca-division-detail"),
]
