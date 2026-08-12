from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from apps.audit.services import record_audit
from apps.users.permissions import IsNCAEditor
from .models import RecordRetentionPolicy, LegalHold, DispositionRun, BackupRun, RestoreDrill, OperationalTaskRun
from .serializers import RetentionPolicySerializer, LegalHoldSerializer, DispositionRunSerializer, BackupRunSerializer, RestoreDrillSerializer, TaskRunSerializer
from .services import readiness_report, preview_disposition


class PolicyListCreate(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]; queryset = RecordRetentionPolicy.objects.all().order_by("record_class", "-version"); serializer_class = RetentionPolicySerializer
    def perform_create(self, serializer): serializer.save(prepared_by=self.request.user)


class HoldListCreate(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]; queryset = LegalHold.objects.all().order_by("-created_at"); serializer_class = LegalHoldSerializer
    def perform_create(self, serializer): serializer.save(created_by=self.request.user)


class DispositionListCreate(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]; queryset = DispositionRun.objects.all().order_by("-requested_at"); serializer_class = DispositionRunSerializer
    def perform_create(self, serializer):
        run = serializer.save(requested_by=self.request.user, dry_run=True)
        preview_disposition(run)


class BackupList(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]; queryset = BackupRun.objects.all().order_by("-started_at"); serializer_class = BackupRunSerializer
class RestoreList(generics.ListCreateAPIView):
    permission_classes = [IsNCAEditor]; queryset = RestoreDrill.objects.all().order_by("-started_at"); serializer_class = RestoreDrillSerializer
class TaskRunList(generics.ListAPIView):
    permission_classes = [IsNCAEditor]; queryset = OperationalTaskRun.objects.all().order_by("-started_at"); serializer_class = TaskRunSerializer


@api_view(["POST"])
@permission_classes([IsNCAEditor])
def approve_policy(request, pk):
    policy = get_object_or_404(RecordRetentionPolicy, pk=pk)
    if not policy.retention_days or not policy.authority_reference: return Response({"detail": "Retention duration and authority reference are required."}, status=400)
    if policy.prepared_by_id == request.user.id: return Response({"detail": "Maker/checker approval requires a different Admin."}, status=409)
    policy.status="APPROVED"; policy.approved_by=request.user; policy.approved_at=timezone.now(); policy.save()
    record_audit(user=request.user, action="RETENTION_POLICY_APPROVED", entity_type="RecordRetentionPolicy", entity_id=pk, after={"version":policy.version})
    return Response(RetentionPolicySerializer(policy).data)


@api_view(["POST"])
@permission_classes([IsNCAEditor])
def release_hold(request, pk):
    hold=get_object_or_404(LegalHold, pk=pk, status="ACTIVE"); hold.status="RELEASED"; hold.released_by=request.user; hold.released_at=timezone.now(); hold.save()
    record_audit(user=request.user, action="LEGAL_HOLD_RELEASED", entity_type="LegalHold", entity_id=pk)
    return Response(LegalHoldSerializer(hold).data)


@api_view(["POST"])
@permission_classes([IsNCAEditor])
def approve_disposition(request, pk):
    run=get_object_or_404(DispositionRun,pk=pk,status="PREVIEWED")
    run.status="APPROVED"; run.approved_by=request.user; run.approved_at=timezone.now(); run.save(update_fields=["status","approved_by","approved_at"])
    record_audit(user=request.user,action="DISPOSITION_RUN_APPROVED",entity_type="DispositionRun",entity_id=run.id,
        after={"dry_run":True,"execution_enabled":False,"certificate_sha256":run.certificate_sha256})
    return Response(DispositionRunSerializer(run).data)


@api_view(["POST"])
@permission_classes([IsNCAEditor])
def sign_off_restore(request, pk):
    drill=get_object_or_404(RestoreDrill,pk=pk,status="PASSED")
    evidence=request.data.get("evidence_reference","").strip()
    if not evidence: return Response({"detail":"evidence_reference is required."},status=400)
    drill.evidence_reference=evidence;drill.signed_off_by=request.user;drill.signed_off_at=timezone.now();drill.save(update_fields=["evidence_reference","signed_off_by","signed_off_at"])
    record_audit(user=request.user,action="RESTORE_DRILL_SIGNED_OFF",entity_type="RestoreDrill",entity_id=drill.id,after={"evidence_reference":evidence})
    return Response(RestoreDrillSerializer(drill).data)


@api_view(["GET"])
@permission_classes([IsNCAEditor])
def readiness(request): return Response(readiness_report())
