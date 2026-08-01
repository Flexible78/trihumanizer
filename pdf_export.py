from __future__ import annotations

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


HEBREW_RANGE = range(0x0590, 0x0600)


def _find_font() -> tuple[str, str | None]:
    candidates = [
        ("Arial", Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf")),
        ("DejaVuSans", Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        ("LiberationSans", Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"), Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf")),
    ]
    for family, regular, bold in candidates:
        if regular.exists():
            pdfmetrics.registerFont(TTFont(family, str(regular)))
            bold_name = None
            if bold.exists():
                bold_name = f"{family}-Bold"
                pdfmetrics.registerFont(TTFont(bold_name, str(bold)))
            return family, bold_name
    return "Helvetica", "Helvetica-Bold"


def _is_hebrew(text: str) -> bool:
    return any(ord(ch) in HEBREW_RANGE for ch in text)


def _display_text(text: str) -> tuple[str, int]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    has_hebrew = _is_hebrew(text)
    for line in text.split("\n"):
        clean = line.rstrip()
        if _is_hebrew(clean):
            clean = get_display(clean)
        lines.append(escape(clean))
    return "<br/>".join(lines), TA_RIGHT if has_hebrew else TA_LEFT


def build_results_pdf(payload: dict) -> bytes:
    buffer = BytesIO()
    font, bold_font = _find_font()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=17 * mm,
        title="TriHumanizer Translator Results",
        author="TriHumanizer Translator",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleCustom",
        parent=styles["Title"],
        fontName=bold_font or font,
        fontSize=17,
        leading=21,
        textColor=colors.HexColor("#17324D"),
        spaceAfter=8,
    )
    meta_style = ParagraphStyle(
        "MetaCustom",
        parent=styles["Normal"],
        fontName=font,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#667085"),
        spaceAfter=10,
    )
    heading_style = ParagraphStyle(
        "HeadingCustom",
        parent=styles["Heading2"],
        fontName=bold_font or font,
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#17324D"),
        spaceBefore=8,
        spaceAfter=5,
    )

    story = [Paragraph("TriHumanizer Translator - Results", title_style)]
    meta = payload.get("meta") or {}
    meta_parts = []
    if meta.get("source_language") or meta.get("target_language"):
        meta_parts.append(f"Language: {escape(str(meta.get('source_language', 'auto')))} -> {escape(str(meta.get('target_language', '')))}")
    if meta.get("mode"):
        meta_parts.append(f"Mode: {escape(str(meta.get('mode')))}")
    if meta.get("provider"):
        meta_parts.append(f"Provider: {escape(str(meta.get('provider')))}")
    if meta.get("model"):
        meta_parts.append(f"Model: {escape(str(meta.get('model')))}")
    if meta_parts:
        story.append(Paragraph(" | ".join(meta_parts), meta_style))

    sections = [
        ("Original text", payload.get("source_text", "")),
        ("Humanized original", payload.get("humanized_original", "")),
        ("Literal translation", payload.get("literal_translation", "")),
        ("Natural translation", payload.get("humanized_translation", "")),
        ("Notes", payload.get("notes", "")),
    ]

    for title, value in sections:
        text = str(value or "").strip()
        if not text:
            continue
        story.append(Paragraph(title, heading_style))
        display, alignment = _display_text(text)
        body_style = ParagraphStyle(
            f"Body{len(story)}",
            parent=styles["BodyText"],
            fontName=font,
            fontSize=10.5,
            leading=15,
            alignment=alignment,
            borderColor=colors.HexColor("#D7DEE7"),
            borderWidth=0.6,
            borderPadding=8,
            backColor=colors.HexColor("#F8FAFC"),
            spaceAfter=7,
        )
        story.append(Paragraph(display, body_style))
        story.append(Spacer(1, 2 * mm))

    doc.build(story)
    return buffer.getvalue()
