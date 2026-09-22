from django.core.management.base import BaseCommand
from django.db import transaction

from apps.submissions.models import ExpectedSubmission, Submission


class Command(BaseCommand):
    help = "Remove the four local demo MNO submissions explicitly created by the demo seed (requires --commit)."

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true")

    def handle(self, *args, **options):
        expected_ids = [128, 129, 130, 131]
        qs = ExpectedSubmission.objects.filter(id__in=expected_ids)
        self.stdout.write(f"Demo targets: {qs.count()} obligations, {Submission.objects.filter(expected_id__in=expected_ids).count()} submissions")
        if not options["commit"]:
            self.stdout.write("Dry run only. Re-run with --commit to remove these exact demo records.")
            return
        with transaction.atomic():
            submissions = Submission.objects.filter(expected_id__in=expected_ids).delete()
            obligations = ExpectedSubmission.objects.filter(id__in=expected_ids).delete()
        self.stdout.write(self.style.SUCCESS(f"Removed submissions={submissions[0]}, obligations={obligations[0]}."))
