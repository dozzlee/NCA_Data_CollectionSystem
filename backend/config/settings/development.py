from .base import *
import dj_database_url

DEBUG = True

# Local workstation fallback. Production remains explicitly PostgreSQL-backed.
DATABASES["default"] = dj_database_url.config(
    default=os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
)

ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = True

INSTALLED_APPS += ["django_extensions"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "True") == "True"
CELERY_TASK_EAGER_PROPAGATES = True
