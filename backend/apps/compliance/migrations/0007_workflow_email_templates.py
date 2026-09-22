from django.db import migrations


TEMPLATES = {
    "FORM_ASSIGNED": (
        "[NCA Compliance] New Form Assigned - {{submission_reference}} - {{period_name}}",
        "Dear Colleague,\n\n{{sender_name}} assigned {{form_name}} ({{form_code}}) for {{period_name}} to {{provider_name}}.\n\nDeadline: {{due_date}}\nRequired next action: Open the assigned form, enter the available indicators and submit it through the provider approval workflow.\n\nOpen the submission: {{portal_link}}\n\nRegards,\nNCA Compliance System",
    ),
    "SUBMITTED_FOR_APPROVAL": (
        "[NCA Compliance] Form Submitted for Approval - {{submission_reference}}",
        "Dear Provider Approver,\n\n{{sender_name}} submitted {{form_name}} for {{period_name}} for provider review.\n\nSubmission: {{submission_reference}}\nCurrent status: {{workflow_status}}\nRequired next action: Review the submitted values, return targeted corrections where necessary, or attest and submit the form to NCA.\n\nOpen the submission: {{portal_link}}",
    ),
    "PROVIDER_RESUBMITTED": (
        "[NCA Compliance] Corrected Form Resubmitted - {{submission_reference}}",
        "Dear Provider Approver,\n\n{{sender_name}} resubmitted corrected data for {{form_name}}, {{period_name}}.\n\nSubmission: {{submission_reference}}\nRequired next action: Review the corrected values and either return further targeted corrections or submit officially to NCA.\n\nOpen the submission: {{portal_link}}",
    ),
    "CORRECTION_REQUEST": (
        "[NCA Compliance] Provider Corrections Required - {{submission_reference}}",
        "Dear Data Entry Team,\n\nThe Provider Approver returned {{form_name}} for {{period_name}}.\n\nSubmission: {{submission_reference}}\nReason: {{reason}}\nCorrection targets: {{correction_targets}}\nRequired next action: Correct the identified indicators and resubmit the form to the Provider Approver.\n\nOpen the submission: {{portal_link}}",
    ),
    "SUBMITTED_TO_NCA": (
        "[NCA Compliance] Submission Sent to NCA - {{submission_reference}}",
        "Dear NCA Review Team,\n\n{{sender_name}} submitted {{form_name}} for {{provider_name}} and {{period_name}} to NCA.\n\nSubmission: {{submission_reference}}\nSubmission date: {{submitted_at}}\nComments: {{comments}}\nRequired next action: Open the submission and begin regulatory review.\n\nOpen the submission: {{portal_link}}",
    ),
    "NCA_ACKNOWLEDGEMENT": (
        "[NCA Compliance] Submission Received - {{submission_reference}}",
        "Dear Provider Team,\n\nNCA acknowledges receipt of {{form_name}} for {{period_name}} from {{provider_name}}.\n\nSubmission: {{submission_reference}}\nDate received: {{submitted_at}}\nThe submission is now available for NCA review. Further communication will appear in the portal and by email.",
    ),
    "NCA_CORRECTION_REQUEST": (
        "[NCA Compliance] NCA Corrections Required - {{submission_reference}}",
        "Dear Provider Approver,\n\nNCA returned {{form_name}} for {{period_name}} for correction.\n\nSubmission: {{submission_reference}}\nReason: {{reason}}\nCorrection targets: {{correction_targets}}\nRequired next action: Review the request, make the corrections or delegate targeted work to Data Entry, then resubmit to NCA.\n\nOpen the submission: {{portal_link}}",
    ),
    "SUBMISSION_REJECTED": (
        "[NCA Compliance] Submission Rejected - {{submission_reference}}",
        "Dear Provider Team,\n\nNCA rejected {{form_name}} for {{period_name}}.\n\nSubmission: {{submission_reference}}\nReason: {{reason}}\nReviewed: {{reviewed_at}}\n\nOpen the submission: {{portal_link}}",
    ),
    "SUBMISSION_APPROVED": (
        "[NCA Compliance] Submission Approved - {{submission_reference}}",
        "Dear Provider Team,\n\nNCA approved {{form_name}} for {{period_name}}.\n\nSubmission: {{submission_reference}}\nReviewed: {{reviewed_at}}\nComments: {{comments}}\n\nOpen the submission: {{portal_link}}",
    ),
    "DEADLINE_CHANGED": (
        "[NCA Compliance] Reporting Deadline Changed - {{submission_reference}}",
        "Dear Provider Team,\n\nThe deadline for {{form_name}}, {{period_name}}, has changed.\n\nSubmission: {{submission_reference}}\nPrevious deadline: {{due_date}}\nRevised deadline: {{revised_due_date}}\nReason: {{reason}}\n\nOpen the submission: {{portal_link}}",
    ),
    "COMPLIANCE_NOTICE": (
        "[NCA Compliance] Compliance Notice - {{submission_reference}}",
        "Dear Provider Approver,\n\nNCA issued a compliance notice for {{form_name}}, {{period_name}}.\n\nSubmission: {{submission_reference}}\nNotice: {{reason}}\nRequired next action: {{next_action}}\n\nOpen the submission: {{portal_link}}",
    ),
    "SUBMISSION_CORRESPONDENCE": (
        "[NCA Compliance] Submission Correspondence - {{submission_reference}}",
        "Dear Colleague,\n\n{{sender_name}} sent correspondence concerning {{form_name}}, {{period_name}}.\n\nSubmission: {{submission_reference}}\nMessage: {{comments}}\n\nOpen the submission: {{portal_link}}",
    ),
}


def add_templates(apps, schema_editor):
    EmailTemplate = apps.get_model("compliance", "EmailTemplate")
    for template_type, (subject, body) in TEMPLATES.items():
        EmailTemplate.objects.get_or_create(
            template_type=template_type,
            version=100,
            defaults={"status": "APPROVED", "subject": subject, "body": body, "placeholders": []},
        )


def remove_templates(apps, schema_editor):
    apps.get_model("compliance", "EmailTemplate").objects.filter(version=100, template_type__in=TEMPLATES).delete()


class Migration(migrations.Migration):
    dependencies = [("compliance", "0006_graphmailboxstate_emaillog_attachments_and_more")]
    operations = [migrations.RunPython(add_templates, remove_templates)]
