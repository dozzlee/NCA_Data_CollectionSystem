from datetime import date, datetime, timezone as dt_timezone

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.submissions.models import ReportingPeriod
from .tasks import _one_calendar_month_before


class ReportingCalendarTests(SimpleTestCase):
    def test_biannual_notice_is_one_calendar_month_before_deadline(self):
        self.assertEqual(_one_calendar_month_before(date(2026, 6, 30)), date(2026, 5, 30))
        self.assertEqual(_one_calendar_month_before(date(2026, 12, 31)), date(2026, 11, 30))

    def test_biannual_period_rejects_any_other_deadline(self):
        period = ReportingPeriod(
            name="Invalid", frequency="SEMI_ANNUAL", year=2026,
            opens_at=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
            due_at=datetime(2026, 6, 29, tzinfo=dt_timezone.utc),
        )
        with self.assertRaises(ValidationError):
            period.clean()

    def test_period_deadline_must_follow_opening(self):
        period = ReportingPeriod(
            name="Invalid", frequency="MONTHLY", year=2026, month=10,
            opens_at=datetime(2026, 10, 1, tzinfo=dt_timezone.utc),
            due_at=datetime(2026, 9, 10, tzinfo=dt_timezone.utc),
        )
        with self.assertRaises(ValidationError):
            period.clean()
