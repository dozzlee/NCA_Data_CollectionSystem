from django.contrib import admin
from .models import FeedbackItem, SystemIssueTicket

admin.site.register(FeedbackItem)
admin.site.register(SystemIssueTicket)
