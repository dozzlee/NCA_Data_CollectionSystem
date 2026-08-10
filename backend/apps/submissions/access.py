from django.shortcuts import get_object_or_404

from .models import ExpectedSubmission, Submission


def expected_submissions_for_user(user):
    queryset = ExpectedSubmission.objects.all()
    if getattr(user, "role", None) in {"NCA_ADMIN", "NCA_OFFICER"}:
        return queryset
    if getattr(user, "is_provider", False) and user.organization_id:
        return queryset.filter(provider__organization_id=user.organization_id)
    return queryset.none()


def submissions_for_user(user):
    queryset = Submission.objects.all()
    if getattr(user, "role", None) in {"NCA_ADMIN", "NCA_OFFICER"}:
        return queryset
    if getattr(user, "is_provider", False) and user.organization_id:
        return queryset.filter(expected__provider__organization_id=user.organization_id)
    return queryset.none()


def get_expected_submission_for_user(user, **lookup):
    return get_object_or_404(expected_submissions_for_user(user), **lookup)


def get_submission_for_user(user, **lookup):
    return get_object_or_404(submissions_for_user(user), **lookup)
