from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.users import views as user_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.users.urls")),
    path("api/v1/nca-divisions/", user_views.NCADivisionListCreateView.as_view()),
    path("api/v1/nca-divisions/<int:pk>/", user_views.NCADivisionDetailView.as_view()),
    path("api/v1/", include("apps.providers.urls")),
    path("api/v1/", include("apps.forms_engine.urls")),
    path("api/v1/", include("apps.submissions.urls")),
    path("api/v1/", include("apps.uploads.urls")),
    path("api/v1/", include("apps.compliance.urls")),
    path("api/v1/", include("apps.exports.urls")),
    path("api/v1/", include("apps.audit.urls")),
    path("api/v1/", include("apps.feedback.urls")),
    path("api/v1/", include("apps.data_requests.urls")),
    path("api/v1/", include("apps.governance.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
