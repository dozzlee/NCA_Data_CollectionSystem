from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("feedback", "0002_systemissueticket_acknowledged_at_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="feedbackitem",
            name="acknowledged_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="feedbackitem",
            name="acknowledged_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="feedback_acknowledged", to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name="FeedbackNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("message", models.TextField()),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("feedback", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="feedback.feedbackitem")),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="feedback_notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="feedbacknotification",
            constraint=models.UniqueConstraint(fields=("feedback", "recipient"), name="unique_feedback_ack_recipient"),
        ),
    ]
