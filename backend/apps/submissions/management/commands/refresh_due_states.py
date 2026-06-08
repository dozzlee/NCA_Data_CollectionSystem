from django.core.management.base import BaseCommand
from apps.submissions.models import ExpectedSubmission


class Command(BaseCommand):
    help = "Recompute due_state for all open expected submissions. Run daily via cron."

    def handle(self, *args, **options):
        qs = ExpectedSubmission.objects.exclude(
            workflow_status__in=["APPROVED", "REJECTED", "ARCHIVED"]
        ).select_related("period")

        updated = 0
        for es in qs.iterator():
            new_state = es.compute_due_state()
            if es.due_state != new_state:
                es.due_state = new_state
                es.save(update_fields=["due_state"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Refreshed {qs.count()} submissions — {updated} due states changed."
        ))
