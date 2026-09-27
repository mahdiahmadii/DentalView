"""
report.py
=========
Generates a PDF dental report for a single case: patient info, the
annotated X-ray (AI boxes + dentist boxes), a findings table split into
"AI-detected findings" and "Dentist diagnosis", and free-text notes.
"""

from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage,
    HRFlowable, PageBreak,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

CLINIC_NAME = "Dental Clinic"  # change this to your clinic's name


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle(name="ReportTitle", fontSize=18, leading=22,
                           textColor=colors.HexColor("#1e2129"), spaceAfter=4,
                           fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle(name="SubTitle", fontSize=10, leading=13,
                           textColor=colors.HexColor("#555555")))
    ss.add(ParagraphStyle(name="SectionHeader", fontSize=13, leading=16,
                           spaceBefore=14, spaceAfter=6,
                           textColor=colors.HexColor("#1e2129"),
                           fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle(name="Body", fontSize=10, leading=14, alignment=TA_LEFT))
    ss.add(ParagraphStyle(name="Small", fontSize=8, leading=11,
                           textColor=colors.HexColor("#777777")))
    return ss


def _patient_info_table(patient: dict, styles):
    data = [
        ["Patient name:", patient.get("full_name", "") or "-",
         "Patient code:", patient.get("patient_code", "") or "-"],
        ["Date of birth:", patient.get("date_of_birth", "") or "-",
         "Sex:", patient.get("sex", "") or "-"],
        ["Phone:", patient.get("phone", "") or "-",
         "Report date:", datetime.now().strftime("%Y-%m-%d %H:%M")],
    ]
    t = Table(data, colWidths=[28 * mm, 55 * mm, 28 * mm, 55 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#2a2a2a")),
    ]))
    return t


def _findings_table(rows, empty_message):
    """rows: list of (class_name, confidence_str, box_str, note)"""
    if not rows:
        return Paragraph(empty_message, ParagraphStyle(
            name="empty", fontSize=9.5, textColor=colors.HexColor("#888888"),
            fontName="Helvetica-Oblique"))
    header = ["Finding", "Confidence", "Location (x1,y1,x2,y2)", "Note"]
    data = [header] + rows
    t = Table(data, colWidths=[45 * mm, 25 * mm, 45 * mm, 51 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2f3542")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f6f8")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def generate_case_report(
    output_path,
    patient: dict,
    case: dict,
    annotated_image_path: str,
    ai_detections: list,
    dentist_detections: list,
    dentist_summary: str = "",
):
    """
    output_path: where to write the .pdf
    patient: dict from db.get_patient()
    case: dict from db.get_case()
    annotated_image_path: path to the PNG/JPG that already has both AI and
        dentist bounding boxes drawn on it
    ai_detections / dentist_detections: list of dicts with keys
        class_name, confidence (may be None for dentist entries), x1,y1,x2,y2, note
    dentist_summary: free-text clinical impression / diagnosis
    """
    styles = _styles()
    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"Dental Report - {patient.get('full_name', '')}",
    )

    story = []

    # ---- Header
    story.append(Paragraph(CLINIC_NAME, styles["ReportTitle"]))
    story.append(Paragraph("Panoramic X-ray (OPG) Analysis Report", styles["SubTitle"]))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dddddd")))
    story.append(Spacer(1, 10))

    # ---- Patient info
    story.append(_patient_info_table(patient, styles))
    if case.get("case_label"):
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<b>Case:</b> {case['case_label']}", styles["Body"]))
    story.append(Spacer(1, 12))

    # ---- Image
    story.append(Paragraph("Analyzed Image", styles["SectionHeader"]))
    img_path = Path(annotated_image_path)
    if img_path.exists():
        from PIL import Image as PILImage
        with PILImage.open(img_path) as im:
            iw, ih = im.size
        max_w = 174 * mm
        max_h = 150 * mm
        scale = min(max_w / iw, max_h / ih)
        story.append(RLImage(str(img_path), width=iw * scale, height=ih * scale))
    else:
        story.append(Paragraph("Image file not found.", styles["Body"]))
    story.append(Paragraph(
        "Colored solid boxes: AI-detected findings. Dashed / labeled \"Dr.\" boxes: "
        "dentist-added findings.", styles["Small"]))
    story.append(Spacer(1, 10))

    # ---- AI findings table
    story.append(Paragraph("AI-Detected Findings", styles["SectionHeader"]))
    ai_rows = [
        [d["class_name"], f"{d['confidence'] * 100:.1f}%" if d.get("confidence") is not None else "-",
         f"({int(d['x1'])}, {int(d['y1'])}, {int(d['x2'])}, {int(d['y2'])})", d.get("note") or ""]
        for d in ai_detections
    ]
    story.append(_findings_table(ai_rows, "No AI findings above the selected confidence threshold."))
    story.append(Spacer(1, 12))

    # ---- Dentist diagnosis table
    story.append(Paragraph("Dentist Diagnosis / Manual Findings", styles["SectionHeader"]))
    dr_rows = [
        [d["class_name"], "-", f"({int(d['x1'])}, {int(d['y1'])}, {int(d['x2'])}, {int(d['y2'])})",
         d.get("note") or ""]
        for d in dentist_detections
    ]
    story.append(_findings_table(dr_rows, "No manual findings were added by the dentist."))
    story.append(Spacer(1, 12))

    # ---- Clinical summary
    story.append(Paragraph("Clinical Impression / Notes", styles["SectionHeader"]))
    summary_text = (dentist_summary or "").strip().replace("\n", "<br/>") or "-"
    story.append(Paragraph(summary_text, styles["Body"]))

    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dddddd")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "This report is generated with the assistance of an AI detection model and is intended "
        "to support, not replace, clinical judgment. All findings should be verified by a licensed "
        "dental professional.", styles["Small"]))

    doc.build(story)
    return str(output_path)
