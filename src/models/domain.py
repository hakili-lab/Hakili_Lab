from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, Field


# ── Qualité image ─────────────────────────────────────────────────────────────

class PageQualityReport(BaseModel):
    page_number: int
    width: int
    height: int
    brightness: float
    blur_variance: float
    issues: list[str] = Field(default_factory=list)
    quality: Literal["good", "poor"]


class QualityReport(BaseModel):
    copy_id: str
    global_quality: Literal["good", "poor"]
    pages: list[PageQualityReport]
    rescan_requested: bool = False


# ── Transcription ──────────────────────────────────────────────────────────────

class PageTranscription(BaseModel):
    page_number: int
    content: str
    formulas: list[str] = Field(default_factory=list)
    diagrams: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class TranscriptionResult(BaseModel):
    copy_id: str
    global_quality: Literal["good", "medium", "poor"]
    pages: list[PageTranscription]


# ── Barème (notation binaire) ──────────────────────────────────────────────────

class RubricItem(BaseModel):
    id: str                      # "Q1", "Q2a", "Q2b"
    label: str
    max_score: Literal[1] = 1   # Toujours 1 — système binaire
    parent_id: str | None = None  # Non-None si sous-question


class Rubric(BaseModel):
    subject: Literal["mathematics"]
    total_points: int
    items: list[RubricItem]


# ── Correction (scores 0 ou 1) ─────────────────────────────────────────────────

class QuestionGrade(BaseModel):
    rubric_item_id: str
    score: Literal[0, 1]
    confidence: float = Field(ge=0.0, le=1.0)
    comment: str
    observed_answer: str
    requires_review: bool


class CopyGrade(BaseModel):
    copy_id: str
    total_score: int
    total_possible: int
    questions: list[QuestionGrade]
    expert_instructions_used: bool = False


# ── Diagnostic et remédiation ─────────────────────────────────────────────────

class SkillAssessment(BaseModel):
    name: str
    level: Literal["mastered", "partial", "weak", "unknown"]
    evidence: str


class RootCauseError(BaseModel):
    """Erreur cachée derrière une erreur visible — cœur du diagnostic pédagogique."""
    visible_error: str
    hidden_cause: str
    linked_questions: list[str] = Field(default_factory=list)


class RemediationItem(BaseModel):
    priority: int
    topic: str
    action: str


class CompetencyGap(BaseModel):
    """Lacune de compétence ancrée sur le programme officiel (résultat du RAG)."""
    chunk_id: str                          # ex: "5e_NUM_Ch3_L1"
    classe: str                            # "5e"
    domaine: str                           # "numerique" | "geometrique"
    chapitre: str
    lecon: str
    description: str                       # texte court de synthèse
    savoir_faire: list[str] = Field(default_factory=list)
    erreurs_frequentes: list[str] = Field(default_factory=list)


class DiagnosticResult(BaseModel):
    copy_id: str
    strengths: list[str]
    weaknesses: list[str]
    root_causes: list[RootCauseError] = Field(default_factory=list)
    skills: list[SkillAssessment]
    remediation_plan: list[RemediationItem]
    competency_gaps: list[CompetencyGap] = Field(default_factory=list)


# ── Sujet de remédiation ───────────────────────────────────────────────────────

class Exercise(BaseModel):
    number: int
    topic: str
    question: str
    hint: str = ""


class RemediationSubject(BaseModel):
    copy_id: str
    exercises: list[Exercise]


# ── Ingestion ────────────────────────────────────────────────────────────────

class IngestionResult(BaseModel):
    copy_id: str
    total_pages: int
    pages: list[Path]  # Paths to extracted images
    output_dir: Path   # Directory containing the pages


# ── Claude API responses ─────────────────────────────────────────────────────

class ClaudeResponse(BaseModel):
    """Generic wrapper for Claude API responses."""
    success: bool
    data: Any  # Parsed Pydantic model (TranscriptionResult, CopyGrade, etc.)
    confidence: float = Field(ge=0.0, le=1.0)
    raw_response: str
    error: str | None = None
