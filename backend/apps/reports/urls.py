from django.urls import path
from . import views

urlpatterns = [
    path("reports/definitions/", views.ReportDefinitionListView.as_view()),
    path("reports/periods/", views.ReportPeriodsView.as_view()),
    path("reports/prepare/", views.ReportPrepareView.as_view()),
    path("reports/preparations/<uuid:pk>/", views.ReportPreparationDetailView.as_view()),
    path("reports/preparations/<uuid:pk>/generate/", views.ReportGenerateView.as_view()),
    path("reports/history/", views.GeneratedReportListView.as_view()),
    path("reports/history/<uuid:pk>/download/", views.GeneratedReportDownloadView.as_view()),
]
