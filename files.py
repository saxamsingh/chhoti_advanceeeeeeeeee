"""Generated files served at /files/{name}. Until the report lanes land these are labelled stub PDFs."""

from __future__ import annotations

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .config import Settings

STUB_FILES = {
    "stub-packet.pdf": "STUB scheme packet. The Subsidy lane replaces this with a prefilled draft.",
    "stub-dossier.pdf": "STUB claim dossier. The Claim lane replaces this with the real evidence dossier.",
}


def ensure_stub_files(settings: Settings) -> None:
    settings.files_dir.mkdir(parents=True, exist_ok=True)
    for name, text in STUB_FILES.items():
        path = settings.files_dir / name
        if path.exists():
            continue
        pdf = canvas.Canvas(str(path), pagesize=A4)
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(56, 780, text)
        pdf.setFont("Helvetica", 11)
        pdf.drawString(56, 750, "Farmer verifies and submits. KhetKaaj never submits for you.")
        pdf.save()
