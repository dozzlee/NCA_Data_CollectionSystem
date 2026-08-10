from django.contrib import admin
from .models import RecordRetentionPolicy, LegalHold, DispositionRun, BackupRun, RestoreDrill, OperationalTaskRun
admin.site.register([RecordRetentionPolicy, LegalHold, DispositionRun, BackupRun, RestoreDrill, OperationalTaskRun])
