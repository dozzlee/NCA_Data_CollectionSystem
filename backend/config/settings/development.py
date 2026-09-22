from .base import *
import dj_database_url

DEBUG = True

# Keep local desktop development on one canonical SQLite database. Older local
# launch commands used ``local-dev.sqlite3`` and could therefore show a
# different form catalogue from the normal development server. Redirect only
# that obsolete local filename; explicit PostgreSQL URLs (including Docker)
# remain unchanged.
database_url = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
if database_url.replace("\\", "/").endswith("/local-dev.sqlite3"):
    database_url = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"

# Local workstation fallback. Production remains explicitly PostgreSQL-backed.
DATABASES["default"] = dj_database_url.parse(database_url)

ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = True
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:3001", "http://localhost:3001"]

INSTALLED_APPS += ["django_extensions"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "True") == "True"
CELERY_TASK_EAGER_PROPAGATES = True
