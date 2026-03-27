from __future__ import annotations

from io import BytesIO
from typing import Any, Dict


def build_enterprise_pdf_report(
    analysis: Dict[str, Any],
    ai_brief: str,
    report_title: str = "Nexus Intelligence Enterprise Technical Assessment",
) -> bytes:
    """Generate a lightweight PDF report for API export."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PDF export requires reportlab. Install with: pip install reportlab") from exc

    table_profiles = analysis.get("table_profiles", []) if isinstance(analysis.get("table_profiles"), list) else []
    relationships = analysis.get("relationships", []) if isinstance(analysis.get("relationships"), list) else []

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=report_title,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#111827"),
        spaceAfter=3,
    )

    summary_rows = [
        ["Generated at", str(analysis.get("generated_at", "n/a"))],
        ["Source type", str(analysis.get("source_type", "n/a"))],
        ["Tables analyzed", str(len(table_profiles))],
        ["Relationships inferred", str(len(relationships))],
        ["Average quality score", str(analysis.get("avg_quality_score", "n/a"))],
    ]

    story = [
        Paragraph(report_title, title_style),
        Paragraph("Enterprise schema, quality, and relationship assessment", body_style),
        Spacer(1, 4),
    ]

    summary_table = Table(summary_rows, colWidths=[45 * mm, 130 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E2E8F0")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#94A3B8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(summary_table)

    if table_profiles:
        story.append(Paragraph("Top Risk Tables", section_style))
        top_risks = sorted(table_profiles, key=lambda x: float(x.get("quality_score", 0) or 0))[:8]
        risk_rows = [["Table", "Quality", "Issues"]]
        for item in top_risks:
            issue_count = len(item.get("issues", [])) if isinstance(item.get("issues"), list) else 0
            risk_rows.append([str(item.get("table", "unknown")), str(item.get("quality_score", "n/a")), str(issue_count)])
        risk_table = Table(risk_rows, colWidths=[80 * mm, 45 * mm, 50 * mm])
        risk_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(risk_table)

    brief_text = str(ai_brief or "").strip()
    if brief_text:
        story.append(Paragraph("AI Executive Brief", section_style))
        for block in [seg.strip() for seg in brief_text.split("\n\n") if seg.strip()]:
            story.append(Paragraph(block.replace("\n", "<br/>"), body_style))

    doc.build(story)
    return buffer.getvalue()
