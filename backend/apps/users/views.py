from django.conf import settings
from ipaddress import ip_address, ip_network
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from apps.audit.services import record_audit
from apps.users.permissions import IsSystemAdmin
from .models import User, Organization, NCADivision
from .serializers import LoginSerializer, UserSerializer, NCADivisionSerializer


def get_client_ip(request):
    direct_peer = request.META.get("REMOTE_ADDR")
    try:
        peer = ip_address(direct_peer)
        trusted = any(peer in ip_network(network, strict=False) for network in settings.TRUSTED_PROXY_CIDRS)
    except (TypeError, ValueError):
        trusted = False
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR") if trusted else None
    return x_forwarded.split(",")[0].strip() if x_forwarded else direct_peer


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            candidate = User.objects.filter(email__iexact=request.data.get("email", "")).first()
            if candidate:
                record_audit(user=candidate, action="USER_LOGIN_FAILED", entity_type="User", entity_id=candidate.id,
                    after={"locked": bool(candidate.locked_until and candidate.locked_until > timezone.now())},
                    ip_address=get_client_ip(request))
            response_status = (
                status.HTTP_401_UNAUTHORIZED
                if "non_field_errors" in serializer.errors
                else status.HTTP_400_BAD_REQUEST
            )
            return Response(serializer.errors, status=response_status)

        user = serializer.validated_data["user"]
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = timezone.now()
        user.save(update_fields=["failed_login_attempts", "locked_until", "last_login_at"])

        refresh = RefreshToken.for_user(user)
        record_audit(user=user, action="USER_LOGIN", entity_type="User", entity_id=user.id, ip_address=get_client_ip(request))
        response = Response({"user": UserSerializer(user).data})
        set_auth_cookies(response, str(refresh.access_token), str(refresh))
        get_token(request)
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            token = RefreshToken(request.COOKIES.get(settings.AUTH_REFRESH_COOKIE) or request.data.get("refresh"))
            token.blacklist()
        except Exception:
            pass
        response = Response({"detail": "Logged out."}, status=status.HTTP_200_OK)
        record_audit(user=request.user, action="USER_LOGOUT", entity_type="User", entity_id=request.user.id,
            ip_address=get_client_ip(request))
        clear_auth_cookies(response)
        return response


def set_auth_cookies(response, access, refresh):
    common = {"httponly": True, "secure": settings.AUTH_COOKIE_SECURE,
              "samesite": settings.AUTH_COOKIE_SAMESITE, "path": "/"}
    response.set_cookie(settings.AUTH_ACCESS_COOKIE, access,
        max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()), **common)
    response.set_cookie(settings.AUTH_REFRESH_COOKIE, refresh,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()), **common)


def clear_auth_cookies(response):
    response.delete_cookie(settings.AUTH_ACCESS_COOKIE, path="/", samesite=settings.AUTH_COOKIE_SAMESITE)
    response.delete_cookie(settings.AUTH_REFRESH_COOKIE, path="/", samesite=settings.AUTH_COOKIE_SAMESITE)


@method_decorator(csrf_protect, name="dispatch")
class CookieTokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE)
        if not raw_refresh:
            return Response({"detail": "Refresh session is unavailable."}, status=401)
        serializer = TokenRefreshSerializer(data={"refresh": raw_refresh})
        serializer.is_valid(raise_exception=True)
        response = Response({"detail": "Session refreshed."})
        set_auth_cookies(response, serializer.validated_data["access"], serializer.validated_data.get("refresh", raw_refresh))
        return response


class CSRFTokenView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class UserListView(generics.ListCreateAPIView):
    """
    GET  — System Admin only.
    POST — System Admin only. Creates a new user (any role).
    """
    permission_classes = [IsSystemAdmin]
    serializer_class = UserSerializer
    queryset = User.objects.select_related("organization", "division").all()
    filterset_fields = ["role", "is_active", "division"]
    search_fields = ["email", "name"]
    ordering_fields = ["name", "email", "role", "created_at"]
    ordering = ["name"]

    def perform_create(self, serializer):
        user = serializer.save()
        record_audit(user=self.request.user, action="USER_CREATED", entity_type="User", entity_id=user.id,
            after={"email": user.email, "role": user.role})


class UserDetailView(generics.RetrieveUpdateAPIView):
    """System Admin only — retrieve and update any user."""
    permission_classes = [IsSystemAdmin]
    queryset = User.objects.select_related("organization", "division").all()
    serializer_class = UserSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def perform_update(self, serializer):
        user = serializer.save()
        record_audit(user=self.request.user, action="USER_UPDATED", entity_type="User", entity_id=user.id,
            after={"email": user.email, "role": user.role, "is_active": user.is_active})


class DeactivateUserView(APIView):
    """Toggle user active status. System Admin only."""
    permission_classes = [IsSystemAdmin]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if str(user.id) == str(request.user.id):
            return Response({"detail": "You cannot deactivate your own account."}, status=400)
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        record_audit(user=request.user, action="USER_DEACTIVATED" if not user.is_active else "USER_REACTIVATED",
            entity_type="User", entity_id=user.id)
        return Response({"id": str(user.id), "is_active": user.is_active, "email": user.email})


class AdminPasswordResetView(APIView):
    permission_classes = [IsSystemAdmin]
    throttle_scope = "password_reset"

    def post(self, request, pk):
        user = generics.get_object_or_404(User, pk=pk)
        password = str(request.data.get("temporary_password", ""))
        from django.contrib.auth.password_validation import validate_password
        try:
            validate_password(password, user)
        except Exception as exc:
            return Response({"detail": " ".join(getattr(exc, "messages", [str(exc)]))}, status=400)
        user.set_password(password)
        user.must_change_password = True
        user.failed_login_attempts = 0
        user.locked_until = None
        user.save(update_fields=["password", "must_change_password", "failed_login_attempts", "locked_until"])
        record_audit(user=request.user, action="USER_TEMPORARY_PASSWORD_ISSUED", entity_type="User", entity_id=user.id)
        return Response({"detail": "Temporary password issued. The user must change it at next sign-in."})


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        current = str(request.data.get("current_password", ""))
        new_password = str(request.data.get("new_password", ""))
        if not request.user.check_password(current):
            return Response({"detail": "Current password is incorrect."}, status=400)
        from django.contrib.auth.password_validation import validate_password
        try:
            validate_password(new_password, request.user)
        except Exception as exc:
            return Response({"detail": " ".join(getattr(exc, "messages", [str(exc)]))}, status=400)
        request.user.set_password(new_password)
        request.user.must_change_password = False
        request.user.save(update_fields=["password", "must_change_password"])
        record_audit(user=request.user, action="USER_PASSWORD_CHANGED", entity_type="User", entity_id=request.user.id)
        return Response({"detail": "Password changed."})


class NCADivisionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsSystemAdmin]
    serializer_class = NCADivisionSerializer
    queryset = NCADivision.objects.all()
    filterset_fields = ["is_active"]
    search_fields = ["code", "name"]

    def perform_create(self, serializer):
        division = serializer.save()
        record_audit(user=self.request.user, action="NCA_DIVISION_CREATED", entity_type="NCADivision", entity_id=division.id,
            after={"code": division.code, "name": division.name})


class NCADivisionDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsSystemAdmin]
    serializer_class = NCADivisionSerializer
    queryset = NCADivision.objects.all()
    http_method_names = ["get", "patch", "head", "options"]

    def perform_update(self, serializer):
        division = serializer.save()
        record_audit(user=self.request.user, action="NCA_DIVISION_UPDATED", entity_type="NCADivision", entity_id=division.id,
            after={"code": division.code, "name": division.name, "is_active": division.is_active})
