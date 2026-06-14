"""
Pipeline Hakili Lab — Correction assistée par IA.

Flux en deux phases :
  Phase A : ingestion → transcription → correction IA → (arrêt : validation enseignant)
  Phase B : RAG → diagnostic → remédiation → export PDF + JSON

  L'interface appelle run_phase_a(), présente le tableau de validation à l'enseignant,
  puis appelle run_phase_b() une fois la validation complète.

Routage multi-providers (contrôlé par .env) :
  Transcription  → VISION_PROVIDER      : "gemini" | "claude"
  Correction     → GRADING_PROVIDER     : "deepseek" | "claude"
  Diagnostic     → DIAGNOSTIC_PROVIDER  : "deepseek" | "mistral" | "claude"
  Remédiation    → REMEDIATION_PROVIDER : "mistral" | "deepseek" | "claude"
  Fallback automatique sur Claude si la clé API du provider est absente.
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from src.api.claude_client import ClaudeClient
from src.core.config import settings
from src.knowledge.curriculum_retriever import CurriculumRetriever
from src.models.domain import (
    CompetencyGap,
    CopyGrade,
    DiagnosticResult,
    IngestionResult,
    Rubric,
    RemediationSubject,
    TeacherDecision,
    TranscriptionResult,
)
from src.pipeline.ingestion import ingest_images, ingest_pdf
from src.pipeline.orchestrator import (
    ValidationIssue,
    validate_diagnostic,
    validate_grading,
    validate_remediation,
    validate_transcription,
)
from src.pipeline.pdf_remediation_html import generate_remediation_pdf
from src.pipeline.pdf_report_html import generate_copy_report

# Singleton RAG — chargé une seule fois pour toute la session
_retriever: CurriculumRetriever | None = None


def _get_retriever() -> CurriculumRetriever:
    global _retriever
    if _retriever is None:
        _retriever = CurriculumRetriever()
    return _retriever


logger = logging.getLogger(__name__)


# ── Factories de clients ───────────────────────────────────────────────────────

def _make_transcription_client():
    provider = settings.vision_provider.lower()
    if provider == "gemini" and settings.google_api_key:
        from src.api.gemini_client import GeminiTranscriptionClient
        return GeminiTranscriptionClient()
    if provider == "mistral" and settings.mistral_api_key:
        from src.api.mistral_client import MistralTranscriptionClient
        return MistralTranscriptionClient()
    return ClaudeClient()


def _make_grading_client():
    provider = settings.grading_provider.lower()
    if provider == "deepseek" and settings.deepseek_api_key:
        from src.api.deepseek_client import DeepSeekClient
        return DeepSeekClient()
    return ClaudeClient()


def _make_diagnostic_client():
    provider = settings.diagnostic_provider.lower()
    if provider == "deepseek" and settings.deepseek_api_key:
        from src.api.deepseek_client import DeepSeekClient
        return DeepSeekClient()
    if provider == "mistral" and settings.mistral_api_key:
        from src.api.mistral_client import MistralRemediationClient
        return MistralRemediationClient()
    return ClaudeClient()


def _make_remediation_client():
    provider = settings.remediation_provider.lower()
    if provider == "mistral" and settings.mistral_api_key:
        from src.api.mistral_client import MistralRemediationClient
        return MistralRemediationClient()
    if provider == "deepseek" and settings.deepseek_api_key:
        from src.api.deepseek_client import DeepSeekClient
        return DeepSeekClient()
    return ClaudeClient()


def _client_label(client, step: str = "") -> str:
    cls = type(client).__name__
    if cls == "GeminiTranscriptionClient":
        return f"Gemini · {getattr(client, '_model', settings.gemini_model)}"
    if cls == "MistralTranscriptionClient":
        return f"Mistral · {settings.mistral_vision_model}"
    if cls == "DeepSeekClient":
        if step == "diagnostic":
            return f"DeepSeek R1 · {settings.deepseek_model_r1}"
        return f"DeepSeek V3 · {settings.deepseek_model_v3}"
    if cls == "MistralRemediationClient":
        return f"Mistral Small · {settings.mistral_model}"
    if step == "diagnostic":
        return f"Claude Opus · {settings.claude_model_opus}"
    return f"Claude · {settings.claude_model_heavy}"


# ── Résultat du pipeline ──────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    copy_id: str
    student_name: str
    ingestion: IngestionResult
    transcription: TranscriptionResult | None = None
    grade: CopyGrade | None = None
    diagnostic: DiagnosticResult | None = None
    remediation_subject: RemediationSubject | None = None
    pdf_path: Path | None = None
    remediation_pdf_path: Path | None = None
    json_path: Path | None = None
    errors: list[str] = field(default_factory=list)
    validation_issues: list[ValidationIssue] = field(default_factory=list)
    model_routing: dict[str, str] = field(default_factory=dict)
    # rubric conservé pour la Phase B
    rubric: Rubric | None = None
    subject_text: str = ""
    bareme_id: str = ""
    runs_dir: str = ""

    @property
    def success(self) -> bool:
        return self.grade is not None and not self.errors

    @property
    def phase_a_complete(self) -> bool:
        return self.grade is not None

    @property
    def phase_b_complete(self) -> bool:
        return self.pdf_path is not None


# ── Phase A — ingestion → transcription → correction IA ──────────────────────

def run_phase_a(
    *,
    copy_id: str,
    student_name: str = "",
    file_paths: list[Path],
    rubric: Rubric,
    rubric_file_path: Path | None = None,
    subject_text: str = "",
    subject_file_path: Path | None = None,
    expert_instructions: str = "",
    bareme_id: str = "",
    official_answers: str = "",
    runs_dir: Path | None = None,
    on_progress: Callable[[str, int], None] | None = None,
) -> PipelineResult:
    """
    Phase A : ingestion → transcription → correction IA.
    Retourne un PipelineResult avec grade.validation_complete = False.
    Le pipeline s'arrête ici — l'enseignant doit valider via le tableau.
    """
    sentinel = PipelineResult(
        copy_id=copy_id,
        student_name=student_name,
        ingestion=None,  # type: ignore[arg-type]
    )
    try:
        return _run_phase_a(
            copy_id=copy_id,
            student_name=student_name,
            file_paths=file_paths,
            rubric=rubric,
            rubric_file_path=rubric_file_path,
            subject_text=subject_text,
            subject_file_path=subject_file_path,
            expert_instructions=expert_instructions,
            bareme_id=bareme_id,
            official_answers=official_answers,
            runs_dir=runs_dir,
            on_progress=on_progress,
        )
    except Exception as exc:
        logger.exception("[%s] Erreur Phase A : %s", copy_id, exc)
        sentinel.errors.append(f"Erreur Phase A : {exc}")
        return sentinel


def _run_phase_a(
    *,
    copy_id: str,
    student_name: str,
    file_paths: list[Path],
    rubric: Rubric,
    rubric_file_path: Path | None,
    subject_text: str,
    subject_file_path: Path | None,
    expert_instructions: str,
    bareme_id: str,
    official_answers: str,
    runs_dir: Path | None,
    on_progress: Callable[[str, int], None] | None,
) -> PipelineResult:

    def _progress(step: str, pct: int) -> None:
        if on_progress:
            try:
                on_progress(step, pct)
            except Exception:
                pass

    out = Path(runs_dir or settings.runs_dir)
    claude_client = ClaudeClient()
    transcription_client = _make_transcription_client()
    grading_client = _make_grading_client()

    logger.warning(
        "[%s] Phase A — transcription=%s | grading=%s",
        copy_id, type(transcription_client).__name__, type(grading_client).__name__,
    )

    # Extraction parallèle énoncé + barème si nécessaire
    need_subject = not subject_text.strip() and subject_file_path is not None
    need_rubric  = not rubric.items and rubric_file_path is not None

    if need_subject and need_rubric:
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_s = pool.submit(claude_client.extract_subject, subject_file_path)
            fut_r = pool.submit(claude_client.extract_rubric, rubric_file_path)
            subject_text = fut_s.result()
            rubric_resp  = fut_r.result()
        if rubric_resp.success and rubric_resp.data is not None:
            rubric = rubric_resp.data
    elif need_subject:
        subject_text = claude_client.extract_subject(subject_file_path)
    elif need_rubric:
        rubric_resp = claude_client.extract_rubric(rubric_file_path)
        if rubric_resp.success and rubric_resp.data is not None:
            rubric = rubric_resp.data

    # 1. Ingestion
    _progress("ingestion", 5)
    if len(file_paths) == 1 and file_paths[0].suffix.lower() == ".pdf":
        ingestion = ingest_pdf(file_paths[0], copy_id, out)
    else:
        ingestion = ingest_images(file_paths, copy_id, out)

    # Extraction nom élève si placeholder
    _name_is_placeholder = (
        not student_name.strip()
        or student_name.strip().replace(" ", "").isdigit()
        or len(student_name.strip()) <= 2
    )
    if _name_is_placeholder and ingestion.pages:
        extracted = claude_client.extract_student_name(ingestion.pages[0])
        if extracted:
            student_name = extracted

    result = PipelineResult(
        copy_id=copy_id,
        student_name=student_name,
        ingestion=ingestion,
        rubric=rubric,
        subject_text=subject_text,
        bareme_id=bareme_id,
        runs_dir=str(out),
    )
    result.model_routing = {
        "Transcription": _client_label(transcription_client, "transcription"),
        "Correction (proposition IA)": _client_label(grading_client, "grading"),
        "Extraction (barème/énoncé)": f"Claude · {settings.claude_model_heavy}",
    }

    # 2. Transcription
    _progress("transcription", 20)
    trans_resp = transcription_client.transcribe(copy_id, ingestion.pages)
    if not trans_resp.success or trans_resp.data is None:
        if type(transcription_client).__name__ != "ClaudeClient":
            logger.warning("[%s] Fallback transcription → Claude", copy_id)
            trans_resp = claude_client.transcribe(copy_id, ingestion.pages)
            result.model_routing["Transcription"] += f" → Claude (fallback)"
    if not trans_resp.success or trans_resp.data is None:
        result.errors.append(f"Transcription échouée : {trans_resp.error}")
        return result

    vt = validate_transcription(trans_resp.data)
    result.validation_issues.extend(vt.issues)
    if not vt.valid:
        result.errors.append(f"Transcription invalide : {vt.summary}")
        return result
    result.transcription = vt.data

    # Barème virtuel si aucun barème fourni
    if not rubric.items:
        rubric = claude_client.extract_questions_from_transcription(result.transcription)
        result.rubric = rubric

    # 3. Correction IA (proposition)
    _progress("correction", 50)
    # Sans barème (mode personnalisé ou extraction échouée), seul Claude peut auto-résoudre
    # les questions — DeepSeek/Mistral ne font pas de self-solving sur rubric vide.
    _grading = claude_client if not rubric.items else grading_client
    if _grading is not grading_client:
        logger.warning("[%s] Aucun barème disponible — correction déléguée à Claude (auto-résolution)", copy_id)
        result.model_routing["Correction (proposition IA)"] = f"Claude · {settings.claude_model_heavy} (auto)"

    grade_resp = _grading.grade(
        transcription=result.transcription,
        rubric=rubric,
        subject_text=subject_text,
        expert_instructions=expert_instructions,
        official_answers=official_answers,
        temperature=0,
    )
    if not grade_resp.success or grade_resp.data is None:
        if type(_grading).__name__ != "ClaudeClient":
            logger.warning("[%s] Fallback correction → Claude", copy_id)
            grade_resp = claude_client.grade(
                transcription=result.transcription,
                rubric=rubric,
                subject_text=subject_text,
                expert_instructions=expert_instructions,
                official_answers=official_answers,
                temperature=0,
            )
            result.model_routing["Correction (proposition IA)"] += " → Claude (fallback)"
    if not grade_resp.success or grade_resp.data is None:
        result.errors.append(f"Correction échouée : {grade_resp.error}")
        return result

    grade = grade_resp.data
    grade.copy_id = copy_id

    vg = validate_grading(grade, rubric_provided=bool(rubric.items), rubric=rubric)
    result.validation_issues.extend(vg.issues)
    if not vg.valid:
        result.errors.append(f"Correction invalide : {vg.summary}")
        return result

    result.grade = vg.data

    # Injecter les bonnes réponses officielles du corrigé dans chaque question
    if bareme_id:
        from src.knowledge.answer_loader import get_answer_loader
        answer_map = get_answer_loader().get_answer_map(bareme_id)
        if answer_map:
            for q in result.grade.questions:
                if not q.correct_answer and q.rubric_item_id in answer_map:
                    q.correct_answer = answer_map[q.rubric_item_id]

    _progress("awaiting_validation", 60)
    _denom = result.grade.total_possible
    _score_20 = round(round(result.grade.total_score / _denom * 20 * 4) / 4, 2) if _denom else 0
    logger.warning(
        "[%s] ✓ Phase A terminée — %d questions, score IA : %g/%g pts → %.2f/20 — en attente de validation enseignant",
        copy_id, len(result.grade.questions),
        result.grade.total_score, _denom, _score_20,
    )
    return result


# ── Phase B — RAG → diagnostic → remédiation → export ─────────────────────────

def run_phase_b(
    *,
    result: PipelineResult,
    on_progress: Callable[[str, int], None] | None = None,
) -> PipelineResult:
    """
    Phase B : RAG + diagnostic + remédiation + export PDF + JSON.
    Reçoit le PipelineResult de la Phase A après validation enseignant.
    result.grade doit avoir compute_final_score() déjà appelé.
    """
    if result.grade is None:
        result.errors.append("Phase B impossible : aucune correction disponible.")
        return result

    # Calcul du score final si pas encore fait
    if result.grade.final_score is None:
        result.grade.compute_final_score()

    sentinel = result
    try:
        return _run_phase_b(result=result, on_progress=on_progress)
    except Exception as exc:
        logger.exception("[%s] Erreur Phase B : %s", result.copy_id, exc)
        sentinel.errors.append(f"Erreur Phase B : {exc}")
        return sentinel


def _run_phase_b(
    *,
    result: PipelineResult,
    on_progress: Callable[[str, int], None] | None,
) -> PipelineResult:

    def _progress(step: str, pct: int) -> None:
        if on_progress:
            try:
                on_progress(step, pct)
            except Exception:
                pass

    copy_id    = result.copy_id
    grade      = result.grade
    rubric     = result.rubric
    bareme_id  = result.bareme_id
    out        = Path(result.runs_dir or settings.runs_dir)

    claude_client      = ClaudeClient()
    diagnostic_client  = _make_diagnostic_client()
    remediation_client = _make_remediation_client()

    result.model_routing.update({
        "Diagnostic": _client_label(diagnostic_client, "diagnostic"),
        "Remédiation": _client_label(remediation_client, "remediation"),
    })

    # Détection score parfait (20/20 après validation enseignant)
    is_perfect = (grade.final_score_on_20 or 0) >= 20.0

    if is_perfect:
        # Score parfait → exercices d'enrichissement niveau 2nde/1ère, pas de remédiation
        logger.warning("[%s] Score parfait 20/20 — génération d'exercices d'enrichissement", copy_id)
        _progress("enrichment", 75)
        enrich_resp = claude_client.generate_enrichment_subject(grade, rubric)
        if enrich_resp.success and enrich_resp.data is not None:
            result.remediation_subject = enrich_resp.data
        else:
            logger.warning("[%s] Enrichissement échoué (non bloquant) : %s", copy_id, enrich_resp.error)
    else:
        # Questions échouées après validation enseignant (score final = 0)
        failed_ids = [
            q.rubric_item_id for q in grade.questions
            if _effective_score(q) == 0
        ]

        # 4. RAG curriculum
        _progress("rag", 65)
        retriever = _get_retriever()
        curriculum_context = ""
        competency_gaps: list[CompetencyGap] = []
        if bareme_id and failed_ids:
            curriculum_context = retriever.get_diagnostic_context(failed_ids, bareme_id)
            raw_gaps = retriever.get_competency_gaps(failed_ids, bareme_id)
            competency_gaps = [CompetencyGap(**g) for g in raw_gaps]
            logger.info(
                "[%s] RAG — %d lacunes pour %d questions échouées (barème: %s)",
                copy_id, len(competency_gaps), len(failed_ids), bareme_id,
            )

        # 5. Diagnostic
        _progress("diagnostic", 75)
        diag_resp = diagnostic_client.diagnose(grade, curriculum_context=curriculum_context)
        if not diag_resp.success or diag_resp.data is None:
            if type(diagnostic_client).__name__ != "ClaudeClient":
                logger.warning("[%s] Fallback diagnostic → Claude", copy_id)
                diag_resp = claude_client.diagnose(grade, curriculum_context=curriculum_context)
        if diag_resp.success and diag_resp.data is not None:
            diag_resp.data.competency_gaps = competency_gaps
            vd = validate_diagnostic(diag_resp.data, grade)
            result.validation_issues.extend(vd.issues)
            result.diagnostic = vd.data
        else:
            logger.warning("[%s] Diagnostic échoué (non bloquant) : %s", copy_id, diag_resp.error)

        # 6. Remédiation
        _progress("remediation", 87)
        if result.diagnostic is not None:
            rem_resp = remediation_client.generate_remediation_subject(result.diagnostic)
            if not rem_resp.success or rem_resp.data is None:
                if type(remediation_client).__name__ != "ClaudeClient":
                    logger.warning("[%s] Fallback remédiation → Claude", copy_id)
                    rem_resp = claude_client.generate_remediation_subject(result.diagnostic)
            if rem_resp.success and rem_resp.data is not None:
                vr = validate_remediation(rem_resp.data, result.diagnostic)
                result.validation_issues.extend(vr.issues)
                result.remediation_subject = vr.data

    # 7. Export JSON
    _progress("export", 94)
    json_dir = out / copy_id
    json_dir.mkdir(parents=True, exist_ok=True)
    json_path = json_dir / "result.json"
    payload = {
        "copy_id": copy_id,
        "student_name": result.student_name,
        "final_score": grade.final_score,
        "final_score_on_20": grade.final_score_on_20,
        "total_possible": grade.total_possible,
        "transcription": result.transcription.model_dump() if result.transcription else None,
        "grade": grade.model_dump(),
        "diagnostic": result.diagnostic.model_dump() if result.diagnostic else None,
        "remediation_subject": result.remediation_subject.model_dump() if result.remediation_subject else None,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    result.json_path = json_path

    # 8. Génération PDF (rapport + remédiation/enrichissement en parallèle)
    pdf_path = json_dir / "rapport_correction.pdf"
    _is_enrich = getattr(result.remediation_subject, "is_enrichment", False)
    remediation_pdf_path = json_dir / (
        "sujet_enrichissement.pdf" if _is_enrich else "sujet_remediation.pdf"
    )
    has_remediation = bool(result.remediation_subject and result.remediation_subject.exercises)

    def _gen_report() -> None:
        generate_copy_report(
            output_path=pdf_path,
            copy_id=copy_id,
            student_name=result.student_name,
            grade=grade,
            diagnostic=result.diagnostic,
            rubric=rubric,
        )

    def _gen_remediation() -> None:
        if has_remediation:
            generate_remediation_pdf(
                output_path=remediation_pdf_path,
                copy_id=copy_id,
                student_name=result.student_name,
                remediation_subject=result.remediation_subject,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        pool.submit(_gen_report).result()
        pool.submit(_gen_remediation).result()

    result.pdf_path = pdf_path
    if has_remediation:
        result.remediation_pdf_path = remediation_pdf_path

    n_exercises = len(result.remediation_subject.exercises) if result.remediation_subject else 0
    logger.warning(
        "[%s] ✓ Phase B terminée — note finale : %g/%g (%.1f/20) | %d exercices remédiation",
        copy_id,
        grade.final_score or 0, grade.total_possible,
        grade.final_score_on_20 or 0,
        n_exercises,
    )
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _effective_score(q) -> float:
    """Score effectif d'une question : décision enseignant si disponible, sinon IA."""
    from src.models.domain import TeacherDecision
    if q.teacher_decision == TeacherDecision.refused and q.teacher_score is not None:
        return q.teacher_score
    return q.score


# ── Wrapper de compatibilité (mode batch / tests) ─────────────────────────────

def run_single_copy(
    *,
    copy_id: str,
    student_name: str = "",
    file_paths: list[Path],
    rubric: Rubric,
    rubric_file_path: Path | None = None,
    subject_text: str = "",
    subject_file_path: Path | None = None,
    expert_instructions: str = "",
    bareme_id: str = "",
    official_answers: str = "",
    runs_dir: Path | None = None,
    on_progress: Callable[[str, int], None] | None = None,
) -> PipelineResult:
    """
    Wrapper pour le mode batch : enchaîne Phase A + validation automatique (tout accepté) + Phase B.
    En mode interactif (traitement unique), utiliser run_phase_a() puis run_phase_b() séparément.
    """
    result = run_phase_a(
        copy_id=copy_id,
        student_name=student_name,
        file_paths=file_paths,
        rubric=rubric,
        rubric_file_path=rubric_file_path,
        subject_text=subject_text,
        subject_file_path=subject_file_path,
        expert_instructions=expert_instructions,
        bareme_id=bareme_id,
        official_answers=official_answers,
        runs_dir=runs_dir,
        on_progress=on_progress,
    )
    if not result.success or result.grade is None:
        return result

    # Validation automatique : tout accepté
    for q in result.grade.questions:
        q.teacher_decision = TeacherDecision.accepted
    result.grade.compute_final_score()

    return run_phase_b(result=result, on_progress=on_progress)
