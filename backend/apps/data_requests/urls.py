from django.urls import path
from . import views

urlpatterns = [
    path("data-catalog/", views.catalog),
    path("data-requests/", views.RequestListCreate.as_view()),
    path("data-requests/<uuid:pk>/", views.RequestDetail.as_view()),
    path("data-requests/<uuid:pk>/start-review/", views.start_review),
    path("data-requests/<uuid:pk>/adjust-delivery/", views.adjust_delivery),
    path("data-requests/<uuid:pk>/request-changes/", views.request_changes),
    path("data-requests/<uuid:pk>/resubmit/", views.resubmit),
    path("data-requests/<uuid:pk>/approve/", views.approve),
    path("data-requests/<uuid:pk>/reject/", views.reject),
    path("data-requests/<uuid:pk>/withdraw/", views.withdraw),
    path("data-requests/<uuid:pk>/retry-generation/", views.retry),
    path("data-requests/<uuid:pk>/download/", views.download),
    path("data-request-notifications/", views.notifications),
    path("data-request-notifications/<int:pk>/mark-read/", views.mark_notification),
    path("data-request-notifications/mark-all-read/", views.mark_all_notifications),
]
