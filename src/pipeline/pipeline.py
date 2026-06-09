"""
Pipeline principal — Hakili Lab.

Flux : ingestion → qualité → transcription → [orchestrateur] → correction
     → [orchestrateur] → diagnostic → [orchestrateur] → remédiation
     → [orchestrateur] → export PDF + JSON

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
    QualityReport,
    Rubric,
    RemediationSubject,
    TranscriptionResult,
)
from src.pipeline.image_quality import assess_copy_quality
from src.pipeline.ingestion import ingest_images, ingest_pdf
from src.pipeline.orchestrator import (
    ValidationIssue,
    validate_diagnostic,
    validate_grading,
    validate_remediation,
    validate_transcription,
)
from src.pipeline.pdf_report import generate_copy_report, generate_remediation_pdf

# Singleton RAG — chargé une seule fois pour toute la session
_retriever: CurriculumRetriever | None = None


def _get_retriever() -> CurriculumRetriever:
    global _retriever
    if _retriever is None:
        _retriever = CurriculumRetriever()
    return _retriever

logger = logging.getLogger(__name__)



# ── Factories de clients (import lazy pour éviter les erreurs au démarrage) ───

def _make_transcription_client():
    """Sélectionne le client de transcription selon VISION_PROVIDER dans .env."""
    provider = settings.vision_provider.lower()
    if provider == "gemini" and settings.google_api_key:
        from src.api.gemini_client import GeminiTranscriptionClient
        return GeminiTranscriptionClient()
    if provider == "mistral" and settings.mistral_api_key:
        from src.api.mistral_client import MistralTranscriptionClient
        return MistralTranscriptionClient()
    return ClaudeClient()


def _make_grading_client():
    """Lit GRADING_PROVIDER dans .env : 'deepseek' | 'claude'."""
    provider = settings.grading_provider.lower()
    if provider == "deepseek" and settings.deepseek_api_key:
        from src.api.deepseek_client import DeepSeekClient
        return DeepSeekClient()
    return ClaudeClient()


def _make_diagnostic_client():
    """Lit DIAGNOSTIC_PROVIDER dans .env : 'deepseek' | 'mistral' | 'claude'."""
    provider = settings.diagnostic_provider.lower()
    if provider == "deepseek" and settings.deepseek_api_key:
        from src.api.deepseek_client import DeepSeekClient
        return DeepSeekClient()
    if provider == "mistral" and settings.mistral_api_key:
        from src.api.mistral_client import MistralRemediationClient
        return MistralRemediationClient()
    return ClaudeClient()


def _make_remediation_client():
    """Lit REMEDIATION_PROVIDER dans .env : 'mistral' | 'deepseek' | 'claude'."""
    provider = settings.remediation_provider.lower()
    if provider == "mistral" and settings.mistral_api_key:
        from src.api.mistral_client import MistralRemediationClient
        return MistralRemediationClient()
    if provider == "deepseek" and settings.deepseek_api_key:
        from src.api.deepseek_client import DeepSeekClient
        return DeepSeekClient()
    return ClaudeClient()


# ── Résultat du pipeline ──────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    copy_id: str
    student_name: str
    ingestion: IngestionResult
    quality: QualityReport
    transcription: TranscriptionResult | None = None
    grade: CopyGrade | None = None
    diagnostic: DiagnosticResult | None = None
    remediation_subject: RemediationSubject | None = None
    pdf_path: Path | None = None
    remediation_pdf_path: Path | None = None
    json_path: Path | None = None
    errors: list[str] = field(default_factory=list)
    # Problèmes détectés par l'orchestrateur, affichés dans l'interface enseignant
    validation_issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.grade is not None and not self.errors


# ── Pipeline principal ────────────────────────────────────────────────────────

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

    def _progress(step: str, pct: int) -> None:
        if on_progress:
            try:
                on_progress(step, pct)
            except Exception:
                pass
    out = Path(runs_dir or settings.runs_dir)

    # Clients spécialisés — initialisés une seule fois par run
    claude_client = ClaudeClient()           # Extraction barème/énoncé (vision + fallback)
    transcription_client = _make_transcription_client()
    grading_client = _make_grading_client()
    diagnostic_client = _make_diagnostic_client()
    remediation_client = _make_remediation_client()

    logger.warning(
        "[%s] MODÈLES — transcription=%s | grading=%s | diagnostic=%s | remédiation=%s",
        copy_id,
        type(transcription_client).__name__,
        type(grading_client).__name__,
        type(diagnostic_client).__name__,
        type(remediation_client).__name__,
    )

    # ── Extraction énoncé (vision) ────────────────────────────────────────────
    if not subject_text.strip() and subject_file_path is not None:
        logger.info("[%s] Extraction texte énoncé…", copy_id)
        subject_text = claude_client.extract_subject(subject_file_path)

    # ── Extraction barème depuis fichier PDF/image ────────────────────────────
    if not rubric.items and rubric_file_path is not None:
        logger.info("[%s] Extraction du barème depuis fichier…", copy_id)
        rubric_resp = claude_client.extract_rubric(rubric_file_path)
        if rubric_resp.success and rubric_resp.data is not None:
            rubric = rubric_resp.data
            logger.info("[%s] Barème extrait : %d items.", copy_id, len(rubric.items))
        else:
            logger.warning("[%s] Extraction barème échouée : %s", copy_id, rubric_resp.error)

    # 1. Ingestion ──────────────────────────────────────────────────────────────
    _progress("ingestion", 5)
    logger.info("[%s] Ingestion (%d fichier(s))…", copy_id, len(file_paths))
    if len(file_paths) == 1 and file_paths[0].suffix.lower() == ".pdf":
        ingestion = ingest_pdf(file_paths[0], copy_id, out)
    else:
        ingestion = ingest_images(file_paths, copy_id, out)

    # Extraction du nom de l'élève depuis la première page si non fourni
    # ou si le nom ressemble à un nom de fichier (chiffres seuls, 1-2 caractères)
    _name_is_placeholder = (
        not student_name.strip()
        or student_name.strip().replace(" ", "").isdigit()
        or len(student_name.strip()) <= 2
    )
    if _name_is_placeholder and ingestion.pages:
        logger.info("[%s] Extraction du nom de l'élève depuis la première page…", copy_id)
        extracted = claude_client.extract_student_name(ingestion.pages[0])
        if extracted:
            student_name = extracted
            logger.info("[%s] Nom extrait : %s", copy_id, student_name)

    result = PipelineResult(
        copy_id=copy_id,
        student_name=student_name,
        ingestion=ingestion,
        quality=QualityReport(copy_id=copy_id, global_quality="good", pages=[], rescan_requested=False),
    )

    # 2. Qualité image ──────────────────────────────────────────────────────────
    logger.info("[%s] Contrôle qualité (%d pages)…", copy_id, ingestion.total_pages)
    result.quality = assess_copy_quality(copy_id, ingestion.pages)

    if result.quality.global_quality == "poor":
        logger.warning("[%s] Qualité insuffisante — traitement poursuivi avec avertissement.", copy_id)

    # 3. Transcription ──────────────────────────────────────────────────────────
    _progress("transcription", 20)
    logger.info("[%s] Transcription (%s)…", copy_id, type(transcription_client).__name__)
    transcription_resp = transcription_client.transcribe(copy_id, ingestion.pages)

    # Fallback Claude si le provider principal échoue (ex: Gemini 429 quota)
    if not transcription_resp.success or transcription_resp.data is None:
        primary_name = type(transcription_client).__name__
        if primary_name != "ClaudeClient":
            logger.warning(
                "[%s] %s échoué — fallback transcription → %s",
                copy_id, primary_name, settings.claude_model_heavy,
            )
            transcription_resp = claude_client.transcribe(copy_id, ingestion.pages)

    if not transcription_resp.success or transcription_resp.data is None:
        result.errors.append(f"Transcription échouée : {transcription_resp.error}")
        return result

    # ── Orchestrateur ① : validation transcription ────────────────────────────
    vt = validate_transcription(transcription_resp.data)
    result.validation_issues.extend(vt.issues)
    if not vt.valid:
        result.errors.append(f"Transcription invalide : {vt.summary}")
        return result
    result.transcription = vt.data

    # 4. Extraction des questions si pas de barème → barème virtuel stable
    #    (temperature=0 : lecture factuelle, une seule fois)
    if not rubric.items:
        logger.info("[%s] Aucun barème fourni — extraction des questions depuis la transcription…", copy_id)
        rubric = claude_client.extract_questions_from_transcription(result.transcription)
        if not rubric.items:
            logger.warning(
                "[%s] Extraction échouée — la correction s'appuiera sur l'auto-détection.",
                copy_id,
            )

    # 5. Correction (passe unique) ─────────────────────────────────────────────
    _progress("correction", 45)
    logger.info("[%s] Correction (%s)…", copy_id, type(grading_client).__name__)
    if official_answers:
        logger.info("[%s] Corrigé officiel disponible (%d chars) — injecté dans le prompt.", copy_id, len(official_answers))
    grade_resp = grading_client.grade(
        transcription=result.transcription,
        rubric=rubric,
        subject_text=subject_text,
        expert_instructions=expert_instructions,
        official_answers=official_answers,
        temperature=0,
    )
    if not grade_resp.success or grade_resp.data is None:
        if type(grading_client).__name__ != "ClaudeClient":
            logger.warning("[%s] %s échoué — fallback correction → Claude", copy_id, type(grading_client).__name__)
            grade_resp = claude_client.grade(
                transcription=result.transcription,
                rubric=rubric,
                subject_text=subject_text,
                expert_instructions=expert_instructions,
                official_answers=official_answers,
                temperature=0,
            )
    if not grade_resp.success or grade_resp.data is None:
        result.errors.append(f"Correction échouée : {grade_resp.error}")
        return result
    merged_grade = grade_resp.data
    merged_grade.copy_id = copy_id
    logger.info("[%s] Correction OK — %d questions", copy_id, len(merged_grade.questions))

    # ── Orchestrateur ② : validation correction ───────────────────────────────
    rubric_provided = bool(rubric.items)
    vg = validate_grading(merged_grade, rubric_provided=rubric_provided)
    result.validation_issues.extend(vg.issues)
    if not vg.valid:
        result.errors.append(f"Correction invalide : {vg.summary}")
        return result
    result.grade = vg.data

    # 6. RAG — récupération du contexte curriculum ────────────────────────────
    _progress("rag", 66)
    retriever = _get_retriever()
    failed_ids = [
        q.rubric_item_id for q in result.grade.questions if q.score == 0
    ]
    curriculum_context = ""
    competency_gaps: list[CompetencyGap] = []
    if bareme_id and failed_ids:
        curriculum_context = retriever.get_diagnostic_context(failed_ids, bareme_id)
        raw_gaps = retriever.get_competency_gaps(failed_ids, bareme_id)
        competency_gaps = [CompetencyGap(**g) for g in raw_gaps]
        if curriculum_context:
            logger.info(
                "[%s] RAG — %d lacunes récupérées pour %d questions échouées (barème: %s)",
                copy_id, len(competency_gaps), len(failed_ids), bareme_id,
            )
        else:
            logger.info(
                "[%s] RAG — barème '%s' sans chunks KB (diagnostic sans contexte curricula)",
                copy_id, bareme_id,
            )

    # 7. Diagnostic ─────────────────────────────────────────────────────────────
    _progress("diagnostic", 76)
    logger.info("[%s] Diagnostic (%s)…", copy_id, type(diagnostic_client).__name__)
    diag_resp = diagnostic_client.diagnose(result.grade, curriculum_context=curriculum_context)
    if not diag_resp.success or diag_resp.data is None:
        if type(diagnostic_client).__name__ != "ClaudeClient":
            logger.warning(
                "[%s] %s échoué — fallback diagnostic → %s",
                copy_id, type(diagnostic_client).__name__, settings.claude_model_light,
            )
            diag_resp = claude_client.diagnose(result.grade, curriculum_context=curriculum_context)
    if diag_resp.success and diag_resp.data is not None:
        diag_resp.data.competency_gaps = competency_gaps
        # ── Orchestrateur ③ : validation diagnostic ───────────────────────────
        vd = validate_diagnostic(diag_resp.data, result.grade)
        result.validation_issues.extend(vd.issues)
        result.diagnostic = vd.data
    else:
        logger.warning("[%s] Diagnostic échoué (non bloquant) : %s", copy_id, diag_resp.error)

    # 8. Sujet de remédiation ─────────────────────────────────────────────────
    _progress("remediation", 87)
    if result.diagnostic is not None:
        logger.info("[%s] Génération du sujet de remédiation (%s)…",
                    copy_id, type(remediation_client).__name__)
        rem_resp = remediation_client.generate_remediation_subject(result.diagnostic)
        if not rem_resp.success or rem_resp.data is None:
            if type(remediation_client).__name__ != "ClaudeClient":
                logger.warning(
                    "[%s] %s échoué — fallback remédiation → %s",
                    copy_id, type(remediation_client).__name__, settings.claude_model_heavy,
                )
                rem_resp = claude_client.generate_remediation_subject(result.diagnostic)
        if rem_resp.success and rem_resp.data is not None:
            # ── Orchestrateur ④ : validation remédiation ─────────────────────
            vr = validate_remediation(rem_resp.data, result.diagnostic)
            result.validation_issues.extend(vr.issues)
            result.remediation_subject = vr.data
            logger.info("[%s] %d exercices générés.", copy_id, len(result.remediation_subject.exercises))
        else:
            logger.warning("[%s] Sujet de remédiation non généré (non bloquant) : %s",
                           copy_id, rem_resp.error)

    # 9. Export JSON ────────────────────────────────────────────────────────────
    _progress("export", 94)
    json_dir = out / copy_id
    json_dir.mkdir(parents=True, exist_ok=True)
    json_path = json_dir / "result.json"
    payload = {
        "copy_id": copy_id,
        "student_name": student_name,
        "quality": result.quality.model_dump(),
        "transcription": result.transcription.model_dump() if result.transcription else None,
        "grade": result.grade.model_dump(),
        "diagnostic": result.diagnostic.model_dump() if result.diagnostic else None,
        "remediation_subject": result.remediation_subject.model_dump() if result.remediation_subject else None,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    result.json_path = json_path

    # 10. Rapport PDF correction ────────────────────────────────────────────────
    logger.info("[%s] Génération PDF rapport correction…", copy_id)
    pdf_path = json_dir / "rapport_correction.pdf"
    generate_copy_report(
        output_path=pdf_path,
        copy_id=copy_id,
        student_name=student_name,
        grade=result.grade,
        diagnostic=result.diagnostic,
        quality=result.quality,
    )
    result.pdf_path = pdf_path

    # 11. PDF sujet de remédiation (document élève) ────────────────────────────
    if result.remediation_subject and result.remediation_subject.exercises:
        logger.info("[%s] Génération PDF sujet de remédiation…", copy_id)
        remediation_pdf_path = json_dir / "sujet_remediation.pdf"
        generate_remediation_pdf(
            output_path=remediation_pdf_path,
            copy_id=copy_id,
            student_name=student_name,
            remediation_subject=result.remediation_subject,
        )
        result.remediation_pdf_path = remediation_pdf_path

    n_exercises = len(result.remediation_subject.exercises) if result.remediation_subject else 0
    logger.warning(
        "[%s] ✓ Pipeline terminé — %d/%d pts | %d exercices remédiation | élève : %s",
        copy_id, result.grade.total_score, result.grade.total_possible,
        n_exercises, result.student_name or "inconnu",
    )
    return result
