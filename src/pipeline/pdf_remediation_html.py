"""
Génération PDF feuille de remédiation via xhtml2pdf (HTML+CSS → PDF, pur Python).
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"

_MONTHS_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _today_fr() -> str:
    d = date.today()
    return f"{d.day} {_MONTHS_FR[d.month]} {d.year}"


# ── Importation de la police déjà enregistrée par pdf_report_html ─────────────

def _get_font_name() -> str:
    """Réutilise la police enregistrée par pdf_report_html si disponible."""
    try:
        from src.pipeline.pdf_report_html import _register_unicode_font
        return _register_unicode_font()
    except Exception:
        return "Helvetica"


# ── Contexte Jinja2 ────────────────────────────────────────────────────────────

def _build_context(
    copy_id: str,
    student_name: str,
    remediation_subject: Any,
) -> dict[str, Any]:
    from src.pipeline.pdf_report_html import _cm

    exercises = remediation_subject.exercises

    topics_seen: list[str] = []
    topic_exos: dict[str, list] = {}
    for ex in exercises:
        key = ex.topic
        if key not in topic_exos:
            topics_seen.append(key)
            topic_exos[key] = []
        topic_exos[key].append(ex)

    series = []
    for idx, topic in enumerate(topics_seen, 1):
        exos = topic_exos[topic]
        series.append({
            "idx": idx,
            "topic": _cm(topic),
            "exercises": [
                {
                    "number":   ex.number,
                    "question": _cm(ex.question),
                    "hint":     _cm(getattr(ex, "hint", "") or ""),
                    "has_hint": bool((getattr(ex, "hint", "") or "").strip()),
                }
                for ex in exos
            ],
        })

    is_enrichment = getattr(remediation_subject, "is_enrichment", False)

    return {
        "STUDENT_NAME":   student_name or copy_id,
        "COPY_ID":        copy_id,
        "DATE":           _today_fr(),
        "series":         series,
        "total":          len(exercises),
        "is_enrichment":  is_enrichment,
        "DOC_TITLE":      "Sujet d'enrichissement — Niveau 2nde" if is_enrichment else "Sujet de remédiation",
        "DOC_SUBTITLE":   "Approfondissement pour élève à score parfait" if is_enrichment else "Exercices ciblés sur les lacunes identifiées",
    }


# ── API publique ───────────────────────────────────────────────────────────────

def generate_remediation_pdf(
    output_path: Path,
    copy_id: str,
    student_name: str,
    remediation_subject: Any,
) -> None:
    """Génère la feuille de remédiation PDF via xhtml2pdf."""
    try:
        from xhtml2pdf import pisa
    except ImportError:
        raise RuntimeError(
            "xhtml2pdf non installé. Lancez : pip install xhtml2pdf>=0.2.14"
        )
    from jinja2 import Environment, FileSystemLoader

    font_name = _get_font_name()

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("remediation_exercises.html.j2")
    ctx = _build_context(copy_id, student_name, remediation_subject)
    ctx["FONT_NAME"] = font_name
    html_content = template.render(**ctx)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as pdf_file:
        result = pisa.CreatePDF(html_content, dest=pdf_file, encoding="utf-8")

    if result.err:
        raise RuntimeError(
            f"xhtml2pdf : {result.err} erreur(s) lors de la génération de {output_path.name}"
        )
    logger.info("[%s] Feuille remédiation PDF générée → %s", copy_id, output_path)
