from django.core.management.base import BaseCommand
from apps.submissions.models import ExpectedSubmission
from apps.submissions.services import create_notifications, provider_users


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
            if new_state in ("DUE_SOON", "DUE_TODAY", "OVERDUE"):
                create_notifications(
                    provider_users(es), f"DEADLINE_{new_state}",
                    f"Submission {new_state.lower().replace('_', ' ')}",
                    f"{es.form_template.name} for {es.period.name} requires attention.",
                    f"/provider/submissions/{es.id}",
                    f"deadline:{es.id}:{new_state}",
                )

        self.stdout.write(self.style.SUCCESS(
            f"Refreshed {qs.count()} submissions — {updated} due states changed."
        ))
