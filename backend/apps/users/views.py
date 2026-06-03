from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditEvent
from .models import User
from .serializers import LoginSerializer, UserSerializer


def get_client_ip(request):
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return x_forwarded.split(",")[0] if x_forwarded else request.META.get("REMOTE_ADDR")


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]
        user.failed_login_attempts = 0
        user.last_login_at = timezone.now()
        user.save(update_fields=["failed_login_attempts", "last_login_at"])

        refresh = RefreshToken.for_user(user)
        AuditEvent.objects.create(
            user=user, user_email=user.email, role=user.role,
            organization=user.organization.name if user.organization else "",
            action="USER_LOGIN", entity_type="User", entity_id=str(user.id),
            ip_address=get_client_ip(request),
        )
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
    queryset = User.objects.select_related("organization").all()
    serializer_class = UserSerializer

    def get_queryset(self):
        if self.request.user.role != "NCA_ADMIN":
            return User.objects.none()
        return super().get_queryset()


class UserDetailView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
