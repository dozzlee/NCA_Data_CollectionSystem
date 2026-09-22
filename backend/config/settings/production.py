from django.core.exceptions import ImproperlyConfigured
from .base import *

DEBUG = False


def csv_env(name):
    return [value.strip() for value in os.environ.get(name, "").split(",") if value.strip()]


ALLOWED_HOSTS = csv_env("ALLOWED_HOSTS")
CORS_ALLOWED_ORIGINS = csv_env("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = csv_env("CSRF_TRUSTED_ORIGINS")

# TLS terminates at the managed ingress. The internal reverse proxy overwrites
# this header, and application containers are not exposed in production.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
TRUSTED_PROXY_CIDRS = csv_env("TRUSTED_PROXY_CIDRS")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
AUTH_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
MALWARE_SCANNER_REQUIRED = True

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

unsafe = []
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 10 or "dev" in SECRET_KEY.lower() or "changeme" in SECRET_KEY.lower(): unsafe.append("SECRET_KEY")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS or any(host in {"localhost", "127.0.0.1"} for host in ALLOWED_HOSTS): unsafe.append("ALLOWED_HOSTS")
if not CORS_ALLOWED_ORIGINS or any(not origin.startswith("https://") for origin in CORS_ALLOWED_ORIGINS): unsafe.append("CORS_ALLOWED_ORIGINS")
if not CSRF_TRUSTED_ORIGINS or any(not origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS): unsafe.append("CSRF_TRUSTED_ORIGINS")
if not TRUSTED_PROXY_CIDRS: unsafe.append("TRUSTED_PROXY_CIDRS")
if not PORTAL_URL.startswith("https://"): unsafe.append("PORTAL_URL")
if len(AUDIT_HMAC_KEY) < 32: unsafe.append("AUDIT_HMAC_KEY")
if TARGET_RPO_MINUTES is None: unsafe.append("TARGET_RPO_MINUTES")
if TARGET_RTO_MINUTES is None: unsafe.append("TARGET_RTO_MINUTES")
if unsafe:
    raise ImproperlyConfigured("Unsafe or missing production settings: " + ", ".join(unsafe))
