from django.urls import path

from .views import AuditEventListView, AuditAnchorListView, VerifyAuditChainView


urlpatterns = [
    path("audit/", AuditEventListView.as_view(), name="audit-event-list"),
    path("audit/anchors/", AuditAnchorListView.as_view()),
    path("audit/verify/", VerifyAuditChainView.as_view()),
]
