from django.urls import path
from . import views

urlpatterns = [
    path("submissions/<int:pk>/communications/", views.SubmissionCommunicationHistoryView.as_view()),
    path("submissions/<int:pk>/communications/send/", views.SubmissionCorrespondenceView.as_view()),
    path("submissions/<int:pk>/communications/email-handoff/", views.SubmissionEmailHandoffView.as_view()),
    path("submissions/<int:pk>/communications/email-handoff/<int:handoff_id>/", views.EmailHandoffStatusView.as_view()),
    path("submissions/<int:pk>/compliance-flags/", views.SubmissionComplianceFlagListView.as_view()),
    path("submissions/<int:pk>/compliance-flags/<int:flag_id>/", views.SubmissionComplianceFlagStatusView.as_view()),
    path("submission-communications/templates/", views.EmailTemplateListView.as_view()),
    path("submission-communications/templates/<int:pk>/approve/", views.ApproveEmailTemplateView.as_view()),
    path("submission-communications/legacy-email-history/", views.LegacyEmailHistoryView.as_view()),
]
