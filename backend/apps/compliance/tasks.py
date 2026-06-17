from celery import shared_task
from django.core.management import call_command


@shared_task
def flag_missing_data_task():
    """Run missing-data compliance flagging asynchronously when Celery is configured."""
    try:
        call_command("flag_missing_data")
        return "Successfully flagged missing data"
    except Exception as exc:
        return f"Error flagging missing data: {exc}"
