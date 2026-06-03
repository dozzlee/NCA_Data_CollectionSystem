from django.urls import path
from . import views

urlpatterns = [
    path("form-templates/", views.FormTemplateListView.as_view(), name="form-template-list"),
    path("form-templates/<int:pk>/", views.FormTemplateDetailView.as_view(), name="form-template-detail"),
    path("kmz-requirements/", views.KMZRequirementListView.as_view(), name="kmz-requirements"),
]
