"""
Génération PDF via XeLaTeX + Jinja2.
Fallback automatique sur ReportLab si xelatex est absent.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
_LOGO_PATH    = Path(__file__).resolve().parent.parent / "ui" / "hakili_logo.png"

_LEVEL_BADGES: dict[str, str] = {
    "acquis":      r"\skillbadge{acquis}",
    "part_acquis": r"\skillbadge{partial}",
    "non_acquis":  r"\skillbadge{weak}",
}


# ── LaTeX escape ──────────────────────────────────────────────────────────────

def _le(text: str) -> str:
    """Échappe les caractères spéciaux LaTeX dans du texte utilisateur."""
    if not text:
        return ""
    text = str(text)
    text = text.replace("\\", r"\textbackslash{}")
    text = text.replace("&",  r"\&")
    text = text.replace("%",  r"\%")
    text = text.replace("$",  r"\$")
    text = text.replace("#",  r"\#")
    text = text.replace("_",  r"\_")
    text = text.replace("{",  r"\{")
    text = text.replace("}",  r"\}")
    text = text.replace("~",  r"\textasciitilde{}")
    text = text.replace("^",  r"\textasciicircum{}")
    return text


def _fmt(v: float) -> str:
    """Formate un score — virgule décimale française."""
    s = str(int(v)) if v == int(v) else f"{v:g}"
    return s.replace(".", ",")


# ── Contexte Jinja2 ───────────────────────────────────────────────────────────

def _effective_score(q: Any) -> float:
    """Score effectif après validation enseignant."""
    try:
        if q.teacher_decision.value == "refused" and q.teacher_score is not None:
            return float(q.teacher_score)
    except AttributeError:
        pass
    return float(q.score)


def _build_context(
    copy_id: str,
    grade: Any,
    diagnostic: Any,
    student_name: str,
    rubric: Any = None,
) -> dict[str, Any]:
    questions = grade.questions
    avg_conf  = (sum(q.confidence for q in questions) / len(questions)) if questions else 0.0
    n_review  = sum(1 for q in questions if q.requires_review)

    # Score final validé ou score IA
    final_score    = grade.final_score    if grade.final_score    is not None else grade.total_score
    final_score_20 = grade.final_score_on_20 if grade.final_score_on_20 is not None else None
    pct = (final_score / grade.total_possible) if grade.total_possible else 0.0

    rubric_pts: dict[str, float] = {}
    if rubric:
        rubric_pts = {item.id: item.max_score for item in (rubric.items or [])}

    # Séparation bonnes / mauvaises réponses
    good_qs = []
    bad_qs  = []
    for q in questions:
        ms  = rubric_pts.get(q.rubric_item_id, 1.0)
        eff = _effective_score(q)
        entry = {
            "id":        _le(q.rubric_item_id),
            "score_fmt": _fmt(eff),
            "max_fmt":   _fmt(ms),
            "conf_pct":  round(q.confidence * 100),
            "comment":   _le(q.comment or ""),
            "observed":  _le(q.observed_answer or "—"),
            "correct":   _le(q.correct_answer  or "—"),
            "review":    q.requires_review,
            "validated_by_teacher": getattr(q, "teacher_decision", None) is not None
                                    and getattr(q, "teacher_decision").value != "pending",
        }
        if eff > 0:
            good_qs.append(entry)
        else:
            bad_qs.append(entry)

    gap_index: dict[str, Any] = {}
    if diagnostic and diagnostic.competency_gaps:
        gap_index = {g.chunk_id: g for g in diagnostic.competency_gaps}

    skills = []
    if diagnostic and diagnostic.skills:
        for sk in diagnostic.skills:
            prog = "---"
            if sk.level in ("non_acquis", "part_acquis") and sk.chunk_ids:
                refs = []
                for cid in sk.chunk_ids:
                    g = gap_index.get(cid)
                    refs.append(_le(f"{g.classe} — {g.chapitre}") if g else _le(cid))
                prog = r" / ".join(refs)
            skills.append({
                "name":     _le(sk.name),
                "level":    sk.level,
                "badge":    _LEVEL_BADGES.get(sk.level, r"{\small\color{HakiliGray}---}"),
                "prog":     prog,
                "evidence": _le(sk.evidence),
            })

    root_causes = []
    if diagnostic and diagnostic.root_causes:
        for rc in diagnostic.root_causes:
            root_causes.append({
                "visible": _le(rc.visible_error),
                "hidden":  _le(rc.hidden_cause),
                "qs":      _le(", ".join(rc.linked_questions) or "—"),
            })

    remediation = []
    if diagnostic and diagnostic.remediation_plan:
        for item in sorted(diagnostic.remediation_plan, key=lambda x: x.priority):
            remediation.append({
                "priority": item.priority,
                "topic":    _le(item.topic),
                "action":   _le(item.action),
            })

    logo_exists = _LOGO_PATH.exists()
    logo_path   = str(_LOGO_PATH.resolve()).replace("\\", "/")

    return {
        "LOGO_PATH":           logo_path,
        "LOGO_EXISTS":         logo_exists,
        "STUDENT_NAME":        _le(student_name or copy_id),
        "COPY_ID":             _le(copy_id),
        "FINAL_SCORE":         _fmt(final_score),
        "FINAL_SCORE_20":      _fmt(final_score_20) if final_score_20 is not None else "—",
        "TOTAL_POSSIBLE":      _fmt(grade.total_possible),
        "AI_CONFIDENCE_PCT":   round(avg_conf * 100),
        "REVIEW_COUNT":        n_review,
        "SCORE_COLOR":         "HakiliGreen" if pct >= 0.5 else "HakiliRed",
        "good_questions":      good_qs,
        "bad_questions":       bad_qs,
        "strengths":           [_le(s) for s in (diagnostic.strengths  if diagnostic else [])],
        "weaknesses":          [_le(w) for w in (diagnostic.weaknesses if diagnostic else [])],
        "skills":              skills,
        "root_causes":         root_causes,
        "remediation":         remediation,
        "has_diagnostic":      bool(diagnostic),
        "competency_gaps":     [
            {
                "chunk_id":  _le(g.chunk_id),
                "classe":    _le(g.classe),
                "domaine":   _le(g.domaine.capitalize()),
                "chapitre":  _le(g.chapitre),
                "lecon":     _le(g.lecon),
                "desc":      _le(g.description),
                "erreurs":   [_le(e) for e in (g.erreurs_frequentes or [])],
            }
            for g in (diagnostic.competency_gaps if diagnostic else [])
        ],
    }


# ── Compilation XeLaTeX ───────────────────────────────────────────────────────

def _compile(tex_content: str, output_path: Path) -> None:
    """Compile LaTeX → PDF en deux passes. Lève RuntimeError en cas d'échec."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_file = Path(tmpdir) / "rapport.tex"
        tex_file.write_text(tex_content, encoding="utf-8")
        cmd = ["xelatex", "-interaction=nonstopmode", "-halt-on-error", str(tex_file)]
        for pass_num in range(2):
            proc = subprocess.run(
                cmd, cwd=tmpdir, capture_output=True,
                text=True, encoding="utf-8", errors="replace",
            )
            if proc.returncode != 0:
                log_tail = proc.stdout[-5000:]
                logger.error("xelatex rapport passe %d échouée :\n%s", pass_num + 1, log_tail)
                raise RuntimeError(
                    f"xelatex rapport passe {pass_num + 1} échouée :\n{log_tail}"
                )

        pdf = Path(tmpdir) / "rapport.pdf"
        if not pdf.exists():
            raise RuntimeError(f"xelatex OK mais rapport.pdf absent dans {tmpdir}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(pdf), str(output_path))


# ── API publique ──────────────────────────────────────────────────────────────

def generate_copy_report(
    output_path: Path,
    copy_id: str,
    grade: Any,
    diagnostic: Any,
    student_name: str = "",
    remediation_subject: Any = None,
    rubric: Any = None,
) -> None:
    """Génère le rapport PDF de correction via XeLaTeX + Jinja2."""
    if not shutil.which("xelatex"):
        raise RuntimeError(
            "xelatex introuvable — installez TeX Live ou MiKTeX pour générer les rapports PDF."
        )

    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template    = env.get_template("rapport_correction.tex.j2")
    ctx         = _build_context(copy_id, grade, diagnostic, student_name, rubric)
    tex_content = template.render(**ctx)
    _compile(tex_content, output_path)
    logger.info("[%s] Rapport PDF LaTeX généré → %s", copy_id, output_path)
