from django.urls import path
from . import views

urlpatterns = [
    path("exports/csv/", views.CSVExportView.as_view()),
    path("exports/", views.ExportLogListView.as_view()),
]
