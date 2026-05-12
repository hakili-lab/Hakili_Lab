"""
Orchestrateur principal du pipeline Hakili Lab.

Flux : ingestion → qualité → transcription → correction → diagnostic → rapport PDF + JSON
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.api.claude_client import ClaudeClient
from src.core.config import settings
from src.models.domain import (
    CopyGrade,
    DiagnosticResult,
    IngestionResult,
    QualityReport,
    Rubric,
    TranscriptionResult,
)
from src.pipeline.image_quality import assess_copy_quality
from src.pipeline.ingestion import ingest_images, ingest_pdf
from src.pipeline.pdf_report import generate_copy_report

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    copy_id: str
    ingestion: IngestionResult
    quality: QualityReport
    transcription: TranscriptionResult | None = None
    grade: CopyGrade | None = None
    diagnostic: DiagnosticResult | None = None
    pdf_path: Path | None = None
    json_path: Path | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.grade is not None and not self.errors


def run_single_copy(
    *,
    copy_id: str,
    file_path: Path,
    rubric: Rubric,
    subject_text: str,
    expert_instructions: str = "",
    runs_dir: Path | None = None,
) -> PipelineResult:
    """
    Traite une copie complète (PDF ou image unique).

    Args:
        copy_id: Identifiant anonyme (ex. E-001).
        file_path: Chemin vers le PDF ou l'image.
        rubric: Barème Pydantic.
        subject_text: Texte de l'énoncé (str brut).
        expert_instructions: Instructions contextuelles optionnelles de l'enseignant.
        runs_dir: Répertoire de sortie (défaut : settings.runs_dir).
    """
    out = Path(runs_dir or settings.runs_dir)
    client = ClaudeClient()

    # 1. Ingestion ──────────────────────────────────────────────────────────────
    logger.info("[%s] Ingestion…", copy_id)
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        ingestion = ingest_pdf(file_path, copy_id, out)
    else:
        ingestion = ingest_images([file_path], copy_id, out)

    result = PipelineResult(copy_id=copy_id, ingestion=ingestion, quality=QualityReport(
        copy_id=copy_id, global_quality="good", pages=[], rescan_requested=False
    ))

    # 2. Qualité image ──────────────────────────────────────────────────────────
    logger.info("[%s] Contrôle qualité (%d pages)…", copy_id, ingestion.total_pages)
    result.quality = assess_copy_quality(copy_id, ingestion.pages)

    if result.quality.global_quality == "poor":
        logger.warning("[%s] Qualité insuffisante — traitement poursuivi avec avertissement.", copy_id)

    # 3. Transcription ──────────────────────────────────────────────────────────
    logger.info("[%s] Transcription…", copy_id)
    transcription_resp = client.transcribe(copy_id, ingestion.pages)
    if not transcription_resp.success or transcription_resp.data is None:
        result.errors.append(f"Transcription échouée : {transcription_resp.error}")
        return result
    result.transcription = transcription_resp.data

    # 4. Correction ─────────────────────────────────────────────────────────────
    logger.info("[%s] Correction…", copy_id)
    grade_resp = client.grade(
        transcription=result.transcription,
        rubric=rubric,
        subject_text=subject_text,
        expert_instructions=expert_instructions,
    )
    if not grade_resp.success or grade_resp.data is None:
        result.errors.append(f"Correction échouée : {grade_resp.error}")
        return result
    result.grade = grade_resp.data
    result.grade.copy_id = copy_id  # garantit l'anonymat

    # 5. Diagnostic ─────────────────────────────────────────────────────────────
    logger.info("[%s] Diagnostic…", copy_id)
    diag_resp = client.diagnose(result.grade)
    if diag_resp.success and diag_resp.data is not None:
        result.diagnostic = diag_resp.data
    else:
        logger.warning("[%s] Diagnostic échoué (non bloquant) : %s", copy_id, diag_resp.error)

    # 6. Export JSON ────────────────────────────────────────────────────────────
    json_dir = out / copy_id
    json_dir.mkdir(parents=True, exist_ok=True)
    json_path = json_dir / "result.json"
    payload = {
        "copy_id": copy_id,
        "quality": result.quality.model_dump(),
        "transcription": result.transcription.model_dump() if result.transcription else None,
        "grade": result.grade.model_dump(),
        "diagnostic": result.diagnostic.model_dump() if result.diagnostic else None,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    result.json_path = json_path

    # 7. Rapport PDF ────────────────────────────────────────────────────────────
    logger.info("[%s] Génération PDF…", copy_id)
    pdf_path = json_dir / "rapport.pdf"
    generate_copy_report(
        output_path=pdf_path,
        copy_id=copy_id,
        grade=result.grade,
        diagnostic=result.diagnostic,
        quality=result.quality,
    )
    result.pdf_path = pdf_path

    logger.info("[%s] Pipeline terminé. Score : %d/%d", copy_id, result.grade.total_score, result.grade.total_possible)
    return result
