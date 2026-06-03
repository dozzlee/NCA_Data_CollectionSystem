from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/summary/", views.DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("dashboard/charts/status-donut/", views.StatusDonutView.as_view(), name="chart-status-donut"),
    path("dashboard/charts/category-completion/", views.CategoryCompletionView.as_view(), name="chart-category-completion"),
    path("dashboard/charts/submission-trend/", views.SubmissionTrendView.as_view(), name="chart-submission-trend"),
    path("dashboard/charts/overdue-by-form/", views.OverdueByFormView.as_view(), name="chart-overdue-by-form"),
    path("periods/", views.ReportingPeriodListView.as_view(), name="period-list"),
    path("periods/<int:pk>/", views.ReportingPeriodDetailView.as_view(), name="period-detail"),
    path("periods/<int:pk>/activate/", views.ActivatePeriodView.as_view(), name="period-activate"),
    path("expected-submissions/", views.ExpectedSubmissionListView.as_view(), name="expected-list"),
    path("expected-submissions/<int:pk>/", views.ExpectedSubmissionDetailView.as_view(), name="expected-detail"),
    path("submissions/<int:pk>/", views.SubmissionDetailView.as_view(), name="submission-detail"),
]
