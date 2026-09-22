from pathlib import Path
import dj_database_url
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-key-change-in-production")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    # Local
    "apps.users",
    "apps.providers",
    "apps.forms_engine",
    "apps.submissions",
    "apps.uploads",
    "apps.compliance",
    "apps.exports",
    "apps.audit",
    "apps.feedback",
    "apps.data_requests",
    "apps.governance",
    "apps.reports",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "config.middleware.TrustedProxyHeaderMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Use project-specific cookie names so legacy localhost sessions from earlier
# authentication implementations cannot conflict with this application.
SESSION_COOKIE_NAME = "nca_sessionid"
CSRF_COOKIE_NAME = "nca_csrftoken"

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

AUTH_USER_MODEL = "users.User"

DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL", "postgresql://nca:nca_dev_pass@localhost:5432/nca_dc"),
        conn_max_age=600,
    )
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Accra"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = os.environ.get("STATIC_ROOT", BASE_DIR / "staticfiles")

MEDIA_URL = "/media/"
MEDIA_ROOT = os.environ.get("MEDIA_ROOT", BASE_DIR / "media")
PRIVATE_EXPORT_ROOT = os.environ.get("PRIVATE_EXPORT_ROOT", BASE_DIR / "private_exports")
PRIVATE_UPLOAD_ROOT = os.environ.get("PRIVATE_UPLOAD_ROOT", BASE_DIR / "private_uploads")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DRF
REST_FRAMEWORK = {
    # `format` is an application-level export parameter. Do not treat it as a
    # renderer override (which would reject ?format=xlsx before the view runs).
    "URL_FORMAT_OVERRIDE": None,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.users.authentication.CookieJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"login": "10/min", "password_reset": "5/hour"},
}

# JWT
from datetime import timedelta
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}
AUTH_ACCESS_COOKIE = "nca_access"
AUTH_REFRESH_COOKIE = "nca_refresh"
AUTH_COOKIE_SAMESITE = "Lax"
AUTH_COOKIE_SECURE = os.environ.get("AUTH_COOKIE_SECURE", "False") == "True"
CORS_ALLOW_CREDENTIALS = True
LOGIN_MAX_FAILURES = int(os.environ.get("LOGIN_MAX_FAILURES", "5"))
LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", "15"))

# File uploads
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10MB in memory
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
MAX_KMZ_UPLOAD_MB = 50
MAX_EXCEL_BACKUP_MB = 20
MALWARE_SCANNER_REQUIRED = os.environ.get("MALWARE_SCANNER_REQUIRED", "False") == "True"
CLAMAV_HOST = os.environ.get("CLAMAV_HOST", "clamav")
CLAMAV_PORT = int(os.environ.get("CLAMAV_PORT", 3310))

SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@nca.org.gh")
FEEDBACK_EMAIL = os.environ.get("FEEDBACK_EMAIL", "feedback@nca.org.gh")

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_BEAT_SCHEDULE = {
    "hourly-reminder-evaluation": {"task": "apps.governance.tasks.evaluate_reminders", "schedule": 3600.0},
    "daily-due-state-refresh": {"task": "apps.governance.tasks.refresh_due_states", "schedule": 86400.0},
    "daily-compliance-reconciliation": {"task": "apps.governance.tasks.reconcile_compliance", "schedule": 86400.0},
    "daily-expiry-retention-evaluation": {"task": "apps.governance.tasks.evaluate_expiry_and_retention", "schedule": 86400.0},
    "daily-audit-anchor": {"task": "apps.governance.tasks.create_daily_audit_anchor", "schedule": 86400.0},
}
RETENTION_DISPOSITION_ENABLED = os.environ.get("RETENTION_DISPOSITION_ENABLED", "False") == "True"
TARGET_RPO_MINUTES = int(os.environ["TARGET_RPO_MINUTES"]) if os.environ.get("TARGET_RPO_MINUTES") else None
TARGET_RTO_MINUTES = int(os.environ["TARGET_RTO_MINUTES"]) if os.environ.get("TARGET_RTO_MINUTES") else None
AUDIT_HMAC_KEY = os.environ.get("AUDIT_HMAC_KEY", "")
PORTAL_URL = os.environ.get("PORTAL_URL", "http://127.0.0.1:3001")
APPROVED_PENALTY_REFERENCE = os.environ.get("APPROVED_PENALTY_REFERENCE", "")
IMMUTABLE_AUDIT_STORAGE_REFERENCE = os.environ.get("IMMUTABLE_AUDIT_STORAGE_REFERENCE", "")
RECOVERY_STORAGE_CONFIGURED = os.environ.get("RECOVERY_STORAGE_CONFIGURED", "False") == "True"
UAT_SIGNOFF_REFERENCE = os.environ.get("UAT_SIGNOFF_REFERENCE", "")
INDUSTRY_DASHBOARD_DATASET = os.environ.get("INDUSTRY_DASHBOARD_DATASET", "")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
TRUSTED_PROXY_CIDRS = [value.strip() for value in os.environ.get(
    "TRUSTED_PROXY_CIDRS", "127.0.0.1/32,::1/128"
).split(",") if value.strip()]

GHANA_REGIONS = [
    "Ahafo", "Ashanti", "Bono", "Bono East", "Central", "Eastern",
    "Greater Accra", "North East", "Northern", "Oti", "Savannah",
    "Upper East", "Upper West", "Volta", "Western", "Western North",
]
