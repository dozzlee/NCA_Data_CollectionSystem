import hashlib
import io
from pathlib import Path
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from .models import SubmissionReceipt


def create_receipt(submission):
    if hasattr(submission, "receipt"): return submission.receipt
    reference = f"NCA-{submission.submitted_at:%Y%m%d}-{submission.id:08d}-V{submission.version}"
    snapshot = {"submission_id": submission.id, "version": submission.version,
        "provider": submission.expected.provider.registered_name, "form_code": submission.expected.form_template.form_code,
        "form_version": submission.expected.form_template.version, "period": submission.expected.period.name,
        "submitted_by": submission.submitted_by.email, "submitted_at": submission.submitted_at.isoformat()}
    out = io.BytesIO(); doc = SimpleDocTemplate(out, pagesize=A4); styles = getSampleStyleSheet()
    story = [Paragraph("NCA Official Submission Receipt", styles["Title"]), Spacer(1, 18), Paragraph(f"Receipt reference: {reference}", styles["Heading2"])]
    for key, value in snapshot.items(): story.append(Paragraph(f"<b>{key.replace('_',' ').title()}:</b> {value}", styles["BodyText"]))
    doc.build(story); content = out.getvalue(); root = Path(settings.PRIVATE_EXPORT_ROOT) / "receipts"; root.mkdir(parents=True, exist_ok=True)
    path = root / f"{reference}.pdf"; path.write_bytes(content)
    return SubmissionReceipt.objects.create(submission=submission, reference=reference, snapshot=snapshot, private_path=str(path),
        file_size=len(content), sha256=hashlib.sha256(content).hexdigest())
