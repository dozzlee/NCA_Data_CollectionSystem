from django.urls import path
from . import views

urlpatterns = [
    path("compliance/", views.ComplianceDashboardView.as_view()),
    path("compliance/flags/", views.ComplianceFlagListView.as_view()),
    path("compliance/email-templates/", views.EmailTemplateListView.as_view()),
    path("compliance/generate-email/", views.GenerateEmailView.as_view()),
    path("compliance/emails/", views.EmailLogListView.as_view()),
    path("compliance/emails/<int:pk>/mark-sent/", views.MarkEmailSentView.as_view()),
]
