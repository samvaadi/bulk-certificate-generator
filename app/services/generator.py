from datetime import date
from io import BytesIO
from jinja2 import Environment, FileSystemLoader, select_autoescape
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from app.config import TEMPLATE_PATH


class CertificateGeneratorService:
    def __init__(self, template_path=TEMPLATE_PATH):
        self.environment = Environment(loader=FileSystemLoader(str(template_path.parent)), autoescape=select_autoescape(["html"]))
        self.template = self.environment.get_template(template_path.name)

    def generate(self, *, event_name: str, issue_date: str | None, recipient_id: str, recipient_name: str, metadata: dict) -> bytes:
        context = {"event_name": event_name, "issue_date": issue_date or date.today().isoformat(), "recipient_id": recipient_id, "recipient_name": recipient_name, "metadata": metadata or {}}
        self.template.render(**context)
        output = BytesIO()
        page = landscape(A4)
        pdf = canvas.Canvas(output, pagesize=page)
        width, height = page
        pdf.setFillColor(HexColor("#f8fafc")); pdf.rect(0, 0, width, height, fill=1, stroke=0)
        pdf.setStrokeColor(HexColor("#0f172a")); pdf.setLineWidth(8); pdf.rect(24, 24, width - 48, height - 48)
        pdf.setStrokeColor(HexColor("#cbd5e1")); pdf.setLineWidth(1); pdf.rect(42, 42, width - 84, height - 84)
        title = metadata.get("certificate_title") or "Certificate of Completion"
        pdf.setFillColor(HexColor("#0f172a")); pdf.setFont("Helvetica-Bold", 24); pdf.drawCentredString(width / 2, height - 105, title[:70].upper())
        pdf.setFillColor(HexColor("#64748b")); pdf.setFont("Helvetica", 11); pdf.drawCentredString(width / 2, height - 135, "THIS IS OFFICIALLY PRESENTED TO")
        pdf.setFillColor(HexColor("#1e3a8a")); pdf.setFont("Helvetica-Bold", 28); pdf.drawCentredString(width / 2, height - 185, recipient_name[:90])
        pdf.setStrokeColor(HexColor("#e2e8f0")); pdf.line(width * .22, height - 200, width * .78, height - 200)
        pdf.setFillColor(HexColor("#334155")); pdf.setFont("Helvetica", 13); pdf.drawCentredString(width / 2, height - 240, "For successful participation and demonstrating excellence in")
        pdf.setFont("Helvetica-Bold", 14); pdf.drawCentredString(width / 2, height - 264, event_name[:100])
        if metadata.get("grade"):
            pdf.setFont("Helvetica-Bold", 11); pdf.drawCentredString(width / 2, height - 295, f"Grade / Result: {str(metadata['grade'])[:80]}")
        pdf.setFont("Helvetica", 10); pdf.drawString(70, 90, f"Date of Issue: {context['issue_date']}")
        pdf.drawString(70, 72, f"Verification ID: {recipient_id}")
        pdf.setStrokeColor(HexColor("#94a3b8")); pdf.line(width - 260, 94, width - 70, 94)
        pdf.setFillColor(HexColor("#475569")); pdf.setFont("Helvetica-Bold", 10); pdf.drawCentredString(width - 165, 77, "Authorized Signatory")
        pdf.setFont("Helvetica", 10); pdf.drawCentredString(width - 165, 61, str(metadata.get("issuer_name") or "Program Director")[:60])
        pdf.save()
        return output.getvalue()
