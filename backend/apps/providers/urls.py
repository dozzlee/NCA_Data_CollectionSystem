from django.urls import path
from . import views

urlpatterns = [
    path("providers/", views.ProviderProfileListView.as_view()),
    path("providers/<int:pk>/", views.ProviderProfileDetailView.as_view()),
]
