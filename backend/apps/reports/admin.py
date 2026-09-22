from django.contrib import admin
from .models import GeneratedReport, ReportPreparation, ReportPublicationMetadata, ReportTemplate

admin.site.register(ReportTemplate)
admin.site.register(ReportPublicationMetadata)
admin.site.register(ReportPreparation)
admin.site.register(GeneratedReport)
