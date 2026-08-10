from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.services import record_audit
from apps.users.permissions import IsSystemAdmin
from .models import User, Organization
from .serializers import LoginSerializer, UserSerializer


def get_client_ip(request):
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return x_forwarded.split(",")[0] if x_forwarded else request.META.get("REMOTE_ADDR")


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            response_status = (
                status.HTTP_401_UNAUTHORIZED
                if "non_field_errors" in serializer.errors
                else status.HTTP_400_BAD_REQUEST
            )
            return Response(serializer.errors, status=response_status)

        user = serializer.validated_data["user"]
        user.failed_login_attempts = 0
        user.last_login_at = timezone.now()
        user.save(update_fields=["failed_login_attempts", "last_login_at"])

        refresh = RefreshToken.for_user(user)
        record_audit(user=user, action="USER_LOGIN", entity_type="User", entity_id=user.id, ip_address=get_client_ip(request))
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            token = RefreshToken(request.data.get("refresh"))
            token.blacklist()
        except Exception:
            pass
        return Response({"detail": "Logged out."}, status=status.HTTP_200_OK)


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
    queryset = User.objects.select_related("organization").all()
    filterset_fields = ["role", "is_active"]
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
    queryset = User.objects.select_related("organization").all()
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
