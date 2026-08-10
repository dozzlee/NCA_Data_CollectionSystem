from django.urls import path
from . import views

urlpatterns = [
    path("governance/retention-policies/", views.PolicyListCreate.as_view()),
    path("governance/retention-policies/<int:pk>/approve/", views.approve_policy),
    path("governance/legal-holds/", views.HoldListCreate.as_view()),
    path("governance/legal-holds/<int:pk>/release/", views.release_hold),
    path("governance/disposition-runs/", views.DispositionListCreate.as_view()),
    path("governance/disposition-runs/<int:pk>/approve/", views.approve_disposition),
    path("governance/backups/", views.BackupList.as_view()),
    path("governance/restore-drills/", views.RestoreList.as_view()),
    path("governance/restore-drills/<int:pk>/sign-off/", views.sign_off_restore),
    path("governance/task-runs/", views.TaskRunList.as_view()),
    path("governance/readiness/", views.readiness),
]
