import pytest
from src.models.domain import (
    QuestionGrade,
    CopyGrade,
    RubricItem,
    Rubric,
    TranscriptionResult,
    PageTranscription,
    DiagnosticResult,
    SkillAssessment,
    RemediationItem,
)


# ── CopyGrade / QuestionGrade ──────────────────────────────────────────────────

def test_question_grade_binary_score():
    q = QuestionGrade(
        rubric_item_id="Q1",
        score=1,
        confidence=0.95,
        comment="Correct.",
        observed_answer="x = 3",
        requires_review=False,
    )
    assert q.score == 1
    assert q.confidence == 0.95


def test_question_grade_zero_score():
    q = QuestionGrade(
        rubric_item_id="Q2a",
        score=0,
        confidence=0.6,
        comment="Réponse absente.",
        observed_answer="[ILLISIBLE]",
        requires_review=True,
    )
    assert q.score == 0
    assert q.requires_review is True


def test_question_grade_rejects_partial_score():
    with pytest.raises(Exception):
        QuestionGrade(
            rubric_item_id="Q3",
            score=0.5,  # type: ignore[arg-type]  # doit être rejeté : Literal[0, 1]
            confidence=0.8,
            comment="Partiel.",
            observed_answer="...",
            requires_review=False,
        )


def test_copy_grade_totals():
    questions = [
        QuestionGrade(
            rubric_item_id="Q1",
            score=1,
            confidence=0.9,
            comment="Correct.",
            observed_answer="2",
            requires_review=False,
        ),
        QuestionGrade(
            rubric_item_id="Q2",
            score=0,
            confidence=0.7,
            comment="Incorrect.",
            observed_answer="3",
            requires_review=False,
        ),
    ]
    grade = CopyGrade(
        copy_id="E-001",
        total_score=1,
        total_possible=2,
        questions=questions,
    )
    assert grade.copy_id == "E-001"
    assert grade.total_score == 1
    assert grade.total_possible == 2
    assert len(grade.questions) == 2


# ── Rubric ─────────────────────────────────────────────────────────────────────

def test_rubric_binary_max_score():
    item = RubricItem(id="Q1", label="Calculer la dérivée")
    assert item.max_score == 1


def test_rubric_sub_question():
    item = RubricItem(id="Q2a", label="Montrer que...", parent_id="Q2")
    assert item.parent_id == "Q2"


def test_rubric_full():
    rubric = Rubric(
        subject="mathematics",
        total_points=3,
        items=[
            RubricItem(id="Q1", label="Factoriser"),
            RubricItem(id="Q2a", label="Calculer f(0)", parent_id="Q2"),
            RubricItem(id="Q2b", label="Calculer f'(0)", parent_id="Q2"),
        ],
    )
    assert rubric.total_points == 3
    assert len(rubric.items) == 3


# ── TranscriptionResult ────────────────────────────────────────────────────────

def test_transcription_result():
    page = PageTranscription(
        page_number=1,
        content="f(x) = x² + 2x",
        formulas=["f(x) = x² + 2x"],
        confidence=0.92,
    )
    result = TranscriptionResult(
        copy_id="E-002",
        global_quality="good",
        pages=[page],
    )
    assert result.copy_id == "E-002"
    assert result.pages[0].confidence == 0.92


def test_transcription_confidence_bounds():
    with pytest.raises(Exception):
        PageTranscription(
            page_number=1,
            content="x",
            confidence=1.5,  # hors [0, 1]
        )


# ── DiagnosticResult ───────────────────────────────────────────────────────────

def test_diagnostic_result():
    diag = DiagnosticResult(
        copy_id="E-001",
        strengths=["Calcul algébrique"],
        weaknesses=["Rédaction"],
        skills=[
            SkillAssessment(name="Calcul", level="mastered", evidence="Toutes les opérations sont correctes."),
            SkillAssessment(name="Rédaction", level="weak", evidence="Absence de justifications."),
        ],
        remediation_plan=[
            RemediationItem(priority=1, topic="Rédaction mathématique", action="Revoir la structure des démonstrations."),
        ],
    )
    assert diag.skills[0].level == "mastered"
    assert diag.remediation_plan[0].priority == 1
