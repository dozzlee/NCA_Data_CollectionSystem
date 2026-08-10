from rest_framework import serializers
from .models import RecordRetentionPolicy, LegalHold, DispositionRun, BackupRun, RestoreDrill, OperationalTaskRun


class RetentionPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = RecordRetentionPolicy
        fields = "__all__"
        read_only_fields = ["prepared_by", "approved_by", "approved_at", "created_at", "status"]


class LegalHoldSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalHold
        fields = "__all__"
        read_only_fields = ["created_by", "released_by", "created_at", "released_at", "status"]


class DispositionRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = DispositionRun
        fields = "__all__"
        read_only_fields = ["requested_by", "approved_by", "status", "candidate_count", "held_count", "disposed_count", "certificate_sha256", "details", "requested_at", "approved_at", "completed_at"]


class BackupRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupRun
        fields = "__all__"


class RestoreDrillSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestoreDrill
        fields = "__all__"


class TaskRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationalTaskRun
        fields = "__all__"
