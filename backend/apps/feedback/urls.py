from django.urls import path
from . import views

urlpatterns = [
    path("feedback/", views.FeedbackView.as_view()),
    path("issues/", views.SystemIssueView.as_view()),
    path("issues/<int:pk>/", views.SystemIssueDetailView.as_view()),
    path("issues/<int:pk>/actions/", views.SystemIssueActionView.as_view()),
]
