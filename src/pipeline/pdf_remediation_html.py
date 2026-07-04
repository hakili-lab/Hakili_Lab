"""
Génération PDF feuille de remédiation via xhtml2pdf (HTML+CSS → PDF, pur Python).
"""
from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"

# ── Découpage des questions en énoncé + tâches numérotées ────────────────────

# Séparation sur ". " suivi d'une majuscule (ponctuation de fin de phrase)
_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-ZÁÉÈÊËÀÂÙÛÎÏÙÛÜ])')

# Sous-questions numérotées : "(1) ... (2) ..." entre parenthèses en ligne, OU
# "1. ...\n2. ..." avec retours à la ligne (les deux styles sont produits par l'IA
# selon le provider). Le marqueur ne suit jamais une majuscule (il commence par
# "(" ou un chiffre en début de ligne), donc _SENT_SPLIT seul ne le détecte jamais.
_STEP_MARKER = re.compile(r'(?:\A|(?<=[.!?])|(?<=\n))[ \t]*\(?(\d+)[.)]\s+')

# Verbes d'action français (infinitif) qui introduisent une tâche
_TASK_VERBS = re.compile(
    r'^(Puis\s+|Ensuite[\s,]+)?(Calculer|Simplifier|R[eé]soudre|Identifier|'
    r'Pr[eé]senter|V[eé]rifier|[EÉé]crire|Montrer|Factoriser|D[eé]composer|'
    r'D[eé]velopper|Trouver|Poser|Exprimer|Justifier|Repr[eé]senter|'
    r'D[eé]terminer|Comparer|Classer|Lister|Conclure|Indiquer|Expliquer|'
    r'D[eé]montrer|Appliquer|D[eé]duire|Utiliser|Dresser|Effectuer|'
    r'R[eé]duire|Donner|Mod[eé]liser|Construire|Tracer|[EÉ]valuer|'
    r'Prouver|[EÉ]tablir|Partager|D[eé]finir|Repr[eé]senter|Calculez|'
    r'Résolvez|Vérifiez|Montrez|Trouvez)\b',
    re.IGNORECASE,
)


def _split_by_step_markers(text: str) -> tuple[str, list[str]] | None:
    """Détecte une séquence numérotée "(1) ... (2) ..." ou "1. ...\n2. ..." et la
    sépare en (énoncé_intro, [tâche1, tâche2, …]). None si aucune séquence
    1, 2, 3, … valide n'est trouvée (évite les faux positifs isolés)."""
    matches = list(_STEP_MARKER.finditer(text))
    nums = [int(m.group(1)) for m in matches]
    if len(nums) < 2 or nums != list(range(1, len(nums) + 1)):
        return None
    intro = text[: matches[0].start()].strip()
    tasks: list[str] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        tasks.append(text[start:end].strip())
    return intro, tasks


def _split_question(text: str) -> tuple[str, list[str]]:
    """
    Découpe le texte d'un exercice en (énoncé_contexte, [tâche1, tâche2, …]).

    Priorité 1 : séquence numérotée "(1) ... (2) ..." ou "1. ...\\n2. ..." (styles dominants).
    Priorité 2 : phrases débutant par un verbe d'action → tâches numérotées.
    Les phrases contextuelles (ex: "Un père a 3 fois…") → énoncé.
    Si aucun marqueur détecté, première phrase = énoncé, reste = tâches.
    """
    text = text.strip()

    by_markers = _split_by_step_markers(text)
    if by_markers is not None:
        intro, tasks = by_markers
        if intro:
            return intro, tasks
        # Pas de contexte avant le marqueur "1" -- le texte démarre directement par la liste
        return tasks[0], tasks[1:]

    sentences = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    if len(sentences) <= 1:
        return text, []

    enonce_parts: list[str] = []
    tasks = []

    for sent in sentences:
        if _TASK_VERBS.match(sent):
            tasks.append(sent)
        elif tasks:
            # Phrase non-tâche après des tâches → rattacher à la dernière tâche
            tasks[-1] = tasks[-1].rstrip('.') + '. ' + sent
        else:
            enonce_parts.append(sent)

    if not tasks:
        # Aucun verbe d'action → première phrase = énoncé, reste = tâches
        return enonce_parts[0], enonce_parts[1:]

    return ' '.join(enonce_parts), tasks

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
            "topic":     _cm(topic),
            "exercises": exercises_ctx,
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
