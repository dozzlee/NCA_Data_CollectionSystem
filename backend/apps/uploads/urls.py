from django.urls import path
from . import views

urlpatterns = [
    path("submissions/<int:pk>/kmz-uploads/", views.KMZUploadView.as_view()),
    path("submissions/<int:pk>/excel-backups/", views.ExcelBackupUploadView.as_view()),
]
