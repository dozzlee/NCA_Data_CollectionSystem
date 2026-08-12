from django.urls import path
from . import views

urlpatterns = [
    path("providers/", views.ProviderListView.as_view()),
    path("providers/<int:pk>/", views.ProviderDetailView.as_view()),
    path("providers/<int:pk>/contacts/", views.ProviderContactListView.as_view()),
    path("providers/<int:pk>/contacts/<int:cid>/", views.ProviderContactDetailView.as_view()),
    path("provider-form-assignments/", views.ProviderFormAssignmentListCreateView.as_view()),
    path("provider-form-assignments/import/", views.ProviderFormAssignmentImportView.as_view()),
    path("provider-form-assignments/import-template/", views.ProviderFormAssignmentImportTemplateView.as_view()),
]
