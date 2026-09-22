from celery import shared_task

from .models import MonthlyReportArtifact, Submission
from .monthly_reports import generate_monthly_report


@shared_task(bind=True, max_retries=2)
def generate_monthly_report_task(self, submission_id):
    try:
        return generate_monthly_report(submission_id).id
    except Exception as exc:
        submission = Submission.objects.filter(pk=submission_id).first()
        if submission:
            MonthlyReportArtifact.objects.filter(submission=submission).update(
                status="FAILED", error_message=str(exc),
            )
        raise
