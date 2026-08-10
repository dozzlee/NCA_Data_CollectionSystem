from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.permissions import IsSystemAdmin

from .models import AuditEvent, AuditAnchor
from .services import verify_chain
from .serializers import AuditEventSerializer


class AuditEventListView(generics.ListAPIView):
    """Read-only immutable audit trail for System Administrators."""

    permission_classes = [IsSystemAdmin]
    serializer_class = AuditEventSerializer
    queryset = AuditEvent.objects.select_related("user").all()
    filterset_fields = ["role", "action", "entity_type", "entity_id"]
    search_fields = ["user_email", "organization", "action", "entity_type", "entity_id"]
    ordering_fields = ["timestamp", "action", "user_email"]
    ordering = ["-timestamp"]


class AuditAnchorListView(APIView):
    permission_classes=[IsSystemAdmin]
    def get(self,request):
        return Response([{"id":row.id,"anchor_date":row.anchor_date,"first_event_id":row.first_event_id,
            "last_event_id":row.last_event_id,"event_count":row.event_count,"root_hash":row.root_hash,
            "signature":row.signature,"exported_reference":row.exported_reference,"created_at":row.created_at}
            for row in AuditAnchor.objects.order_by("-anchor_date")[:366]])


class VerifyAuditChainView(APIView):
    permission_classes=[IsSystemAdmin]
    def get(self,request):
        problems=verify_chain();return Response({"valid":not problems,"problem_event_ids":problems,"event_count":AuditEvent.objects.count()})
