from django.contrib import admin
from .models import FeedbackItem, FeedbackNotification, SystemIssueTicket

admin.site.register(FeedbackItem)
admin.site.register(FeedbackNotification)
admin.site.register(SystemIssueTicket)
