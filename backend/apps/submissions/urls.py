from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path("dashboard/summary/", views.DashboardSummaryView.as_view()),
    path("dashboard/charts/status-donut/", views.StatusDonutView.as_view()),
    path("dashboard/charts/category-completion/", views.CategoryCompletionView.as_view()),
    path("dashboard/charts/submission-trend/", views.SubmissionTrendView.as_view()),
    path("dashboard/charts/overdue-by-form/", views.OverdueByFormView.as_view()),
    # Periods
    path("periods/", views.ReportingPeriodListView.as_view()),
    path("periods/<int:pk>/", views.ReportingPeriodDetailView.as_view()),
    path("periods/<int:pk>/activate/", views.ActivatePeriodView.as_view()),
    # Expected submissions
    path("expected-submissions/", views.ExpectedSubmissionListView.as_view()),
    path("expected-submissions/<int:pk>/", views.ExpectedSubmissionDetailView.as_view()),
    path("expected-submissions/<int:pk>/start/", views.StartSubmissionView.as_view()),
    # Submissions
    path("submissions/<int:pk>/", views.SubmissionDetailView.as_view()),
    path("submissions/<int:pk>/sections/<str:section_code>/values/", views.SectionValuesView.as_view()),
    path("submissions/<int:pk>/completion/", views.SubmissionCompletionView.as_view()),
    path("submissions/<int:pk>/submit-for-approval/", views.SubmitForApprovalView.as_view()),
    path("submissions/<int:pk>/official-submit/", views.OfficialSubmitView.as_view()),
]
