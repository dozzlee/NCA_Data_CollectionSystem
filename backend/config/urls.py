from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.users.urls")),
    path("api/v1/", include("apps.providers.urls")),
    path("api/v1/", include("apps.forms_engine.urls")),
    path("api/v1/", include("apps.submissions.urls")),
    path("api/v1/", include("apps.uploads.urls")),
    path("api/v1/", include("apps.compliance.urls")),
    path("api/v1/", include("apps.exports.urls")),
    path("api/v1/", include("apps.audit.urls")),
    path("api/v1/", include("apps.feedback.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
