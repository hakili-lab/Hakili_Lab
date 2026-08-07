"""
Génération PDF feuille de remédiation via xhtml2pdf (HTML+CSS → PDF, pur Python).
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

# Découpage question et titre de série : centralisés dans text_structuring
# (partagés avec l'UI). Alias soulignés conservés : usages internes et tests
# existants inchangés.
from src.pipeline.text_structuring import (
    series_title as _series_title,
    split_question as _split_question,
)

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
        exercises_ctx = []
        for ex in exos:
            enonce_raw, tasks_raw = _split_question(str(ex.question))
            exercises_ctx.append({
                "number":    ex.number,
                "enonce":    _cm(enonce_raw),
                "tasks":     [_cm(t) for t in tasks_raw],
                "has_tasks": bool(tasks_raw),
                "hint":      _cm(getattr(ex, "hint", "") or ""),
                "has_hint":  bool((getattr(ex, "hint", "") or "").strip()),
            })
        series.append({
            "idx":       idx,
            "topic":     _cm(_series_title(topic)),
            "exercises": exercises_ctx,
        })

    is_enrichment = getattr(remediation_subject, "is_enrichment", False)
    # Une ConfirmationSubject n'a pas d'attribut `is_enrichment` — seule une
    # RemediationSubject enrichissement en porte un à True. Le duck-typing sur
    # le nom de classe distingue le troisième cas sans dépendance circulaire
    # vers src.models.domain (importé par le pipeline, pas l'inverse ici).
    is_confirmation = type(remediation_subject).__name__ == "ConfirmationSubject"
    is_verification = type(remediation_subject).__name__ == "VerificationSubject"

    _TITRES_VERIFICATION = {
        "T3": (
            "Sujet de vérification (T3)",
            "Vérifie si la remédiation a fait disparaître les difficultés confirmées",
        ),
        "T4": (
            "Contrôle de rétention (T4 — 45 jours)",
            "Vérifie si les acquis résolus tiennent encore 45 jours plus tard",
        ),
        "T5": (
            "Contrôle de rétention (T5 — 3 mois)",
            "Vérifie si les acquis résolus tiennent encore 3 mois plus tard",
        ),
    }

    if is_confirmation:
        doc_kind = "confirmation"
        doc_title = "Sujet de confirmation des lacunes (T1)"
        doc_subtitle = "Vérifie si les difficultés repérées à la première évaluation sont réelles"
    elif is_verification:
        doc_kind = "verification"
        doc_title, doc_subtitle = _TITRES_VERIFICATION.get(
            getattr(remediation_subject, "type_evaluation", ""),
            ("Sujet de vérification", "Vérifie si les problèmes ciblés sont résolus"),
        )
    elif is_enrichment:
        doc_kind = "enrichment"
        doc_title = "Sujet d'enrichissement — Niveau 2nde"
        doc_subtitle = "Approfondissement pour élève à score parfait"
    else:
        doc_kind = "remediation"
        doc_title = "Sujet de remédiation"
        doc_subtitle = "Exercices ciblés sur les lacunes identifiées"

    return {
        "STUDENT_NAME":   student_name or copy_id,
        "COPY_ID":        copy_id,
        "DATE":           _today_fr(),
        "series":         series,
        "total":          len(exercises),
        "doc_kind":       doc_kind,
        "DOC_TITLE":      doc_title,
        "DOC_SUBTITLE":   doc_subtitle,
    }


# ── API publique ───────────────────────────────────────────────────────────────

def generate_remediation_pdf(
    output_path: Path,
    copy_id: str,
    student_name: str,
    remediation_subject: Any,
) -> None:
    """Génère la feuille de remédiation (ou de confirmation T1, de vérification
    T3/rétention T4-T5, ou d'enrichissement) en PDF via xhtml2pdf — le contenu de
    `remediation_subject` (`RemediationSubject`, `ConfirmationSubject` ou
    `VerificationSubject`) détermine laquelle."""
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
