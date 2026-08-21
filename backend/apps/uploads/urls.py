from django.urls import path
from . import views

urlpatterns = [
    path("submissions/<int:pk>/kmz-uploads/", views.KMZUploadView.as_view()),
    path("submissions/<int:pk>/kmz-uploads/<int:uid>/download/", views.KMZDownloadView.as_view()),
    path("submissions/<int:pk>/kmz-uploads/<int:uid>/review/", views.KMZReviewView.as_view()),
    path("submissions/<int:pk>/excel-backups/", views.ExcelBackupListView.as_view()),
    path("submissions/<int:pk>/excel-backups/upload/", views.ExcelBackupUploadView.as_view()),
    path("submissions/<int:pk>/excel-backups/<int:bid>/download/", views.ExcelBackupDownloadView.as_view()),
    path("submissions/<int:pk>/field-attachments/", views.FieldAttachmentView.as_view()),
    path("submissions/<int:pk>/field-attachments/<int:field_id>/", views.FieldAttachmentView.as_view()),
    path("submissions/<int:pk>/field-attachments/files/<int:uid>/download/", views.FieldAttachmentDownloadView.as_view()),
]
