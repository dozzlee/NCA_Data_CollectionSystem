from django.urls import path
from . import views

urlpatterns = [
    path("submissions/<int:pk>/kmz-uploads/", views.KMZUploadView.as_view()),
    path("submissions/<int:pk>/kmz-uploads/<int:uid>/download/", views.KMZDownloadView.as_view()),
    path("submissions/<int:pk>/kmz-uploads/<int:uid>/review/", views.KMZReviewView.as_view()),
    path("submissions/<int:pk>/excel-backups/", views.ExcelBackupListView.as_view()),
    path("submissions/<int:pk>/excel-backups/upload/", views.ExcelBackupUploadView.as_view()),
]
