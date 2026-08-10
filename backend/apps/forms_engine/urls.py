from django.urls import path
from . import views

urlpatterns = [
    # Form Templates
    path("form-templates/",                                         views.FormTemplateListView.as_view()),
    path("form-templates/<int:pk>/",                                views.FormTemplateDetailView.as_view()),
    path("form-families/",                                         views.FormFamilyListCreate.as_view()),
    path("form-families/<int:pk>/approve-frequency/",             views.ApproveFrequencyDecisionView.as_view()),
    path("form-templates/<int:pk>/clone/",                         views.CloneFormVersionView.as_view()),
    path("form-templates/<int:pk>/approve/",                       views.ApproveFormVersionView.as_view()),
    path("form-templates/<int:pk>/publication-checks/",            views.PublicationChecksView.as_view()),
    path("form-templates/<int:pk>/validation-rules/",              views.ValidationRuleListCreate.as_view()),
    path("form-templates/<int:pk>/sections/",                       views.SectionListCreateView.as_view()),
    path("form-templates/<int:pk>/sections/<int:sid>/",             views.SectionDetailView.as_view()),
    path("form-templates/<int:pk>/sections/<int:sid>/fields/",      views.FieldListCreateView.as_view()),
    path("form-templates/<int:pk>/sections/<int:sid>/fields/<int:fid>/", views.FieldDetailView.as_view()),
    path("form-templates/<int:pk>/sections/<int:sid>/grids/",       views.GridListCreateView.as_view()),
    path("form-templates/<int:pk>/sections/<int:sid>/grids/<int:gid>/", views.GridDetailView.as_view()),
    path("grids/<int:gid>/columns/",                                views.GridColumnCreateView.as_view()),
    path("grids/<int:gid>/rows/",                                   views.GridRowCreateView.as_view()),
    # Period assignment
    path("periods/<int:pk>/assign-templates/",                      views.PeriodAssignTemplatesView.as_view()),
    path("periods/<int:pk>/assign-providers/",                      views.PeriodAssignProvidersView.as_view()),
    # KMZ
    path("kmz-requirements/",                                       views.KMZRequirementListView.as_view()),
]
