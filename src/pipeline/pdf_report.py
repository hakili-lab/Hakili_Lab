"""
Génération du rapport PDF — 7 éléments D-CEO-06 :
  1. Note totale + détail par question
  2. Commentaire pédagogique par question
  3. Zones marquées "Révision requise"
  4. Diagnostic des compétences
  5. Plan de remédiation élève
  6. Score de confiance IA
  7. Logo Hakili Lab + numéro anonyme (pas de nom)
"""
from __future__ import annotations

import base64
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from src.models.domain import CopyGrade, DiagnosticResult, QualityReport

_PRIMARY = colors.HexColor("#001F5C")
_LIGHT_BLUE = colors.HexColor("#4A90E2")
_WARN = colors.HexColor("#E67E22")
_GRAY = colors.HexColor("#7F8C8D")
_LIGHT_GRAY = colors.HexColor("#ECF0F1")

_LOGO_PATH = Path(__file__).parent.parent / "ui" / "hakili_logo.png"

W, H = A4
MARGIN = 20 * mm


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Heading1"], textColor=_PRIMARY, fontSize=16, spaceAfter=4),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], textColor=_PRIMARY, fontSize=12, spaceAfter=2),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], textColor=_LIGHT_BLUE, fontSize=10, spaceAfter=2),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=9, leading=13),
        "warn": ParagraphStyle("warn", parent=base["Normal"], fontSize=9, textColor=_WARN),
        "small": ParagraphStyle("small", parent=base["Normal"], fontSize=8, textColor=_GRAY),
        "caption": ParagraphStyle("caption", parent=base["Normal"], fontSize=8, textColor=_GRAY, alignment=1),
    }


def _header_footer(canvas, doc):  # noqa: ANN001
    canvas.saveState()
    # Logo
    if _LOGO_PATH.exists():
        canvas.drawImage(str(_LOGO_PATH), MARGIN, H - 18 * mm, width=12 * mm, height=12 * mm, preserveAspectRatio=True, mask="auto")
    # Titre plateforme
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(_PRIMARY)
    canvas.drawString(MARGIN + 14 * mm, H - 12 * mm, "HAKILI LAB — Rapport de correction IA")
    # Ligne séparatrice
    canvas.setStrokeColor(_LIGHT_BLUE)
    canvas.setLineWidth(1)
    canvas.line(MARGIN, H - 20 * mm, W - MARGIN, H - 20 * mm)
    # Pied de page
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(_GRAY)
    canvas.drawCentredString(W / 2, 10 * mm, f"Page {doc.page} — Document confidentiel — Usage pédagogique exclusif")
    canvas.restoreState()


def generate_copy_report(
    output_path: Path,
    copy_id: str,
    grade: CopyGrade,
    diagnostic: DiagnosticResult | None,
    quality: QualityReport,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    S = _styles()

    doc = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=25 * mm,
        bottomMargin=18 * mm,
    )
    frame = Frame(MARGIN, 18 * mm, W - 2 * MARGIN, H - 43 * mm, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_header_footer)])

    story = []

    # ── En-tête copie ──────────────────────────────────────────────────────────
    story.append(Paragraph(f"Copie : <b>{copy_id}</b>", S["title"]))
    story.append(HRFlowable(width="100%", thickness=2, color=_LIGHT_BLUE, spaceAfter=6))

    # ── 1 & 6 — Note totale + confiance IA ────────────────────────────────────
    avg_conf = (
        sum(q.confidence for q in grade.questions) / len(grade.questions)
        if grade.questions else 0.0
    )
    summary_data = [
        ["Note totale", f"{grade.total_score} / {grade.total_possible}"],
        ["Confiance IA moyenne", f"{avg_conf:.0%}"],
        ["Instructions expert utilisées", "Oui" if grade.expert_instructions_used else "Non"],
    ]
    if quality.global_quality == "poor":
        summary_data.append(["Qualité image", "⚠ Insuffisante"])

    summary_table = Table(summary_data, colWidths=[60 * mm, 80 * mm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), _LIGHT_GRAY),
        ("TEXTCOLOR", (0, 0), (0, -1), _PRIMARY),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (1, 0), (1, 0), 14),
        ("TEXTCOLOR", (1, 0), (1, 0), _PRIMARY),
        ("ALIGN", (1, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUND", (0, 0), (-1, -1), [colors.white, _LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 6 * mm))

    # ── 2 & 3 — Détail par question + commentaires + révision ─────────────────
    story.append(Paragraph("Détail de la correction", S["h2"]))

    q_data = [["Question", "Score", "Confiance", "Commentaire"]]
    review_items = []

    for q in grade.questions:
        score_str = "✓ 1" if q.score == 1 else "✗ 0"
        conf_str = f"{q.confidence:.0%}"
        comment = q.comment[:80] + ("…" if len(q.comment) > 80 else "")
        q_data.append([q.rubric_item_id, score_str, conf_str, comment])
        if q.requires_review:
            review_items.append(q)

    q_table = Table(q_data, colWidths=[25 * mm, 18 * mm, 22 * mm, None])
    q_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (2, -1), "CENTER"),
        ("ROWBACKGROUND", (0, 1), (-1, -1), [colors.white, _LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BDC3C7")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("WORDWRAP", (3, 1), (3, -1), True),
    ]))
    story.append(q_table)
    story.append(Spacer(1, 4 * mm))

    # ── 3 — Zones "révision requise" ──────────────────────────────────────────
    if review_items:
        story.append(Paragraph("⚠ Éléments nécessitant une révision manuelle", S["h2"]))
        for q in review_items:
            story.append(Paragraph(
                f"<b>{q.rubric_item_id}</b> — Réponse observée : <i>{q.observed_answer[:100]}</i>",
                S["warn"],
            ))
        story.append(Spacer(1, 4 * mm))

    # ── 4 — Diagnostic des compétences ────────────────────────────────────────
    if diagnostic:
        story.append(HRFlowable(width="100%", thickness=1, color=_LIGHT_GRAY, spaceAfter=4))
        story.append(Paragraph("Diagnostic des compétences", S["h2"]))

        if diagnostic.strengths:
            story.append(Paragraph("Points forts", S["h3"]))
            for s in diagnostic.strengths:
                story.append(Paragraph(f"• {s}", S["body"]))
            story.append(Spacer(1, 2 * mm))

        if diagnostic.weaknesses:
            story.append(Paragraph("Points à renforcer", S["h3"]))
            for w in diagnostic.weaknesses:
                story.append(Paragraph(f"• {w}", S["body"]))
            story.append(Spacer(1, 2 * mm))

        if diagnostic.skills:
            story.append(Paragraph("Évaluation par compétence", S["h3"]))
            skill_data = [["Compétence", "Niveau", "Observation"]]
            level_labels = {"mastered": "✓ Acquis", "partial": "~ Partiel", "weak": "✗ Fragile", "unknown": "? Inconnu"}
            for sk in diagnostic.skills:
                skill_data.append([sk.name, level_labels.get(sk.level, sk.level), sk.evidence[:60]])
            sk_table = Table(skill_data, colWidths=[45 * mm, 25 * mm, None])
            sk_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), _PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUND", (0, 1), (-1, -1), [colors.white, _LIGHT_GRAY]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BDC3C7")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(sk_table)
            story.append(Spacer(1, 4 * mm))

        # ── 5 — Plan de remédiation ────────────────────────────────────────────
        if diagnostic.remediation_plan:
            story.append(Paragraph("Plan de remédiation personnalisé", S["h2"]))
            for item in sorted(diagnostic.remediation_plan, key=lambda x: x.priority):
                story.append(Paragraph(
                    f"<b>{item.priority}. {item.topic}</b> — {item.action}",
                    S["body"],
                ))
            story.append(Spacer(1, 4 * mm))

    # ── Pied de rapport ────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=_LIGHT_GRAY, spaceAfter=3))
    story.append(Paragraph(
        "Ce rapport est généré par l'IA Hakili Lab. Il doit être validé par l'enseignant avant restitution officielle.",
        S["small"],
    ))

    doc.build(story)
