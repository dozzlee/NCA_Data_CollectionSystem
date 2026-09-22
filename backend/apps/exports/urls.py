from django.urls import path
from . import views

urlpatterns = [
    path("exports/csv/", views.CSVExportView.as_view()),
    path("exports/pdf/", views.PDFExportView.as_view()),
    path("exports/", views.ExportLogListView.as_view()),
    path("exports/catalogue/", views.ExportCatalogueView.as_view()),
    path("exports/catalogue/xlsx/", views.ExportCatalogueWorkbookView.as_view()),
]
