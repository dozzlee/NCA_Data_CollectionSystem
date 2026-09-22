from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate from an HttpOnly cookie and enforce CSRF on unsafe methods."""

    def authenticate(self, request):
        header = self.get_header(request)
        raw_token = self.get_raw_token(header) if header is not None else None
        from_cookie = raw_token is None
        if from_cookie:
            raw_token = request.COOKIES.get(settings.AUTH_ACCESS_COOKIE)
        if raw_token is None:
            return None
        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)
        allowed_for_password_change = {
            "/api/v1/auth/me/", "/api/v1/auth/logout/",
            "/api/v1/auth/change-password/", "/api/v1/auth/csrf/",
        }
        if user.must_change_password and request.path not in allowed_for_password_change:
            raise exceptions.PermissionDenied("Change the temporary password before continuing.")
        if from_cookie and request.method not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            reason = CsrfViewMiddleware(lambda req: None).process_view(request, None, (), {})
            if reason:
                raise exceptions.PermissionDenied("CSRF validation failed.")
        return user, validated_token
