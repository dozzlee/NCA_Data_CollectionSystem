from django.contrib import admin
from .models import DataRequest, DataRequestEvent, DataRequestNotification, DataRequestArtifact

admin.site.register([DataRequest, DataRequestEvent, DataRequestNotification, DataRequestArtifact])
