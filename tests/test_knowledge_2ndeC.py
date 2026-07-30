"""
Tests de validation du test diagnostique 2nde C (hakili_2ndeC_v1).

Vérifie :
  - Cohérence des IDs entre barème et corrigé
  - Total des points = 20.0
  - Chargement via TestRegistry (sans API)
  - Chargement via AnswerLoader (corrigé officiel)
  - Toutes les questions ont un enonce_court et des chunk_ids
  - Toutes les réponses du corrigé sont non vides
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_KB = Path(__file__).parent.parent / "data" / "knowledge"
_BAREME_PATH  = _KB / "bareme_test_2ndeC.yaml"
_CORRIGE_PATH = _KB / "corrige_test_2ndeC.yaml"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def bareme() -> dict:
    return yaml.safe_load(_BAREME_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def corrige() -> dict:
    return yaml.safe_load(_CORRIGE_PATH.read_text(encoding="utf-8"))


def _all_questions(data: dict) -> list[dict]:
    qs = []
    for sec in ("questions_numeriques", "questions_geometriques"):
        qs.extend(data.get(sec, []))
    return qs


# ── Tests fichiers YAML ───────────────────────────────────────────────────────

def test_bareme_file_exists():
    assert _BAREME_PATH.exists(), "bareme_test_2ndeC.yaml introuvable"


def test_corrige_file_exists():
    assert _CORRIGE_PATH.exists(), "corrige_test_2ndeC.yaml introuvable"


def test_bareme_meta(bareme):
    meta = bareme.get("meta", {})
    assert meta.get("test_id") == "hakili_2ndeC_v1"
    assert meta.get("total_possible") == 20
    assert "2nde" in meta.get("niveaux_evalues", [])


def test_corrige_meta(corrige):
    meta = corrige.get("meta", {})
    assert meta.get("test_id") == "hakili_2ndeC_v1"


def test_total_questions_count(bareme):
    qs = _all_questions(bareme)
    assert len(qs) == 54, f"Attendu 54 sous-questions, trouvé {len(qs)}"


def test_total_points_equals_20(bareme):
    total = sum(float(q.get("points_originaux", 0)) for q in _all_questions(bareme))
    assert total == pytest.approx(20.0), f"Total points : {total} ≠ 20.0"


def test_numeriques_points(bareme):
    total_num = sum(
        float(q.get("points_originaux", 0))
        for q in bareme.get("questions_numeriques", [])
    )
    assert total_num == pytest.approx(13.0), f"NUM points : {total_num} ≠ 13.0"


def test_geometriques_points(bareme):
    total_geo = sum(
        float(q.get("points_originaux", 0))
        for q in bareme.get("questions_geometriques", [])
    )
    assert total_geo == pytest.approx(7.0), f"GEO points : {total_geo} ≠ 7.0"


def test_all_bareme_ids_unique(bareme):
    ids = [q["id"] for q in _all_questions(bareme)]
    assert len(ids) == len(set(ids)), f"IDs dupliqués dans le barème : {[i for i in ids if ids.count(i) > 1]}"


def test_all_corrige_ids_unique(corrige):
    ids = [q["id"] for q in _all_questions(corrige)]
    assert len(ids) == len(set(ids)), f"IDs dupliqués dans le corrigé : {[i for i in ids if ids.count(i) > 1]}"


def test_bareme_corrige_ids_match(bareme, corrige):
    bareme_ids  = {q["id"] for q in _all_questions(bareme)}
    corrige_ids = {q["id"] for q in _all_questions(corrige)}
    only_bareme  = bareme_ids  - corrige_ids
    only_corrige = corrige_ids - bareme_ids
    assert not only_bareme,  f"IDs présents dans le barème mais absents du corrigé : {sorted(only_bareme)}"
    assert not only_corrige, f"IDs présents dans le corrigé mais absents du barème : {sorted(only_corrige)}"


def test_all_questions_have_enonce_court(bareme):
    missing = [q["id"] for q in _all_questions(bareme) if not q.get("enonce_court", "").strip()]
    assert not missing, f"Questions sans enonce_court : {missing}"


def test_all_questions_have_chunk_ids(bareme):
    missing = [q["id"] for q in _all_questions(bareme) if not q.get("chunk_ids")]
    assert not missing, f"Questions sans chunk_ids : {missing}"


def test_all_corrige_reponses_non_empty(corrige):
    empty = [q["id"] for q in _all_questions(corrige) if not q.get("reponse", "").strip()]
    assert not empty, f"Questions sans réponse dans le corrigé : {empty}"


def test_all_corrige_solutions_non_empty(corrige):
    empty = [q["id"] for q in _all_questions(corrige) if not str(q.get("solution", "")).strip()]
    assert not empty, f"Questions sans solution dans le corrigé : {empty}"


def test_requires_review_flags(bareme):
    review_ids = {q["id"] for q in _all_questions(bareme) if q.get("requires_review")}
    # Ces questions nécessitent une construction graphique
    expected_review = {"Q_NUM_14f", "Q_GEO_01a", "Q_GEO_02", "Q_GEO_07a", "Q_GEO_07b",
                       "Q_GEO_08a", "Q_GEO_08b", "Q_GEO_08c"}
    missing = expected_review - review_ids
    assert not missing, f"requires_review manquant sur : {sorted(missing)}"


# ── Tests TestRegistry ────────────────────────────────────────────────────────

def test_registry_contains_2ndeC():
    from src.knowledge.test_registry import get_registry
    registry = get_registry()
    assert "hakili_2ndeC_v1" in registry.ids, "hakili_2ndeC_v1 absent du TestRegistry"


def test_registry_2ndeC_rubric_loaded():
    from src.knowledge.test_registry import get_registry
    test = get_registry().get_test("hakili_2ndeC_v1")
    assert test is not None
    assert test.rubric.total_points == pytest.approx(20.0)
    assert len(test.rubric.items) == 54


def test_registry_2ndeC_label():
    from src.knowledge.test_registry import get_registry
    test = get_registry().get_test("hakili_2ndeC_v1")
    assert "2nde" in test.label.lower() or "2nde" in test.niveaux.lower()


# ── Tests AnswerLoader ────────────────────────────────────────────────────────

def test_answer_loader_contains_2ndeC():
    from src.knowledge.answer_loader import get_answer_loader
    loader = get_answer_loader()
    assert "hakili_2ndeC_v1" in loader.available_tests()


def test_answer_loader_2ndeC_all_answers():
    from src.knowledge.answer_loader import get_answer_loader
    answer_map = get_answer_loader().get_answer_map("hakili_2ndeC_v1")
    assert len(answer_map) == 54, f"Attendu 54 réponses, trouvé {len(answer_map)}"


def test_answer_loader_2ndeC_text_block():
    from src.knowledge.answer_loader import get_answer_loader
    text = get_answer_loader().get_official_answers("hakili_2ndeC_v1")
    assert "Corrigé officiel" in text
    assert "Q_NUM_01" in text
    assert "Q_GEO_09b" in text


# ── Tests compute_final_score avec barème 2ndeC ──────────────────────────────

def test_compute_final_score_2ndeC_perfect():
    """Un élève parfait sur le test 2ndeC doit obtenir 20/20."""
    from src.knowledge.test_registry import get_registry
    from src.models.domain import CopyGrade, QuestionGrade, TeacherDecision

    test = get_registry().get_test("hakili_2ndeC_v1")
    questions = [
        QuestionGrade(
            rubric_item_id=item.id,
            score=item.max_score,
            confidence=1.0,
            comment="Correct.",
            observed_answer="ok",
            requires_review=False,
            teacher_decision=TeacherDecision.accepted,
        )
        for item in test.rubric.items
    ]
    grade = CopyGrade(
        copy_id="test-parfait",
        total_score=sum(q.score for q in questions),
        total_possible=20.0,
        questions=questions,
    )
    grade.compute_final_score()
    assert grade.final_score == pytest.approx(20.0)
    assert grade.final_score_on_20 == pytest.approx(20.0)


def test_compute_final_score_2ndeC_zero():
    """Un élève qui n'a rien répondu doit obtenir 0/20."""
    from src.knowledge.test_registry import get_registry
    from src.models.domain import CopyGrade, QuestionGrade, TeacherDecision

    test = get_registry().get_test("hakili_2ndeC_v1")
    questions = [
        QuestionGrade(
            rubric_item_id=item.id,
            score=0.0,
            confidence=0.5,
            comment="Absent.",
            observed_answer="—",
            requires_review=False,
            teacher_decision=TeacherDecision.accepted,
        )
        for item in test.rubric.items
    ]
    grade = CopyGrade(
        copy_id="test-zero",
        total_score=0.0,
        total_possible=20.0,
        questions=questions,
    )
    grade.compute_final_score()
    assert grade.final_score == pytest.approx(0.0)
    assert grade.final_score_on_20 == pytest.approx(0.0)


def test_compute_final_score_teacher_override():
    """La décision enseignant doit primer sur la note IA."""
    from src.knowledge.test_registry import get_registry
    from src.models.domain import CopyGrade, QuestionGrade, TeacherDecision

    test = get_registry().get_test("hakili_2ndeC_v1")
    # Tous acceptés sauf Q_NUM_01 que l'enseignant refuse et met à 0
    questions = [
        QuestionGrade(
            rubric_item_id=item.id,
            score=item.max_score,
            confidence=1.0,
            comment="Correct.",
            observed_answer="ok",
            requires_review=False,
            teacher_decision=(
                TeacherDecision.refused if item.id == "Q_NUM_01" else TeacherDecision.accepted
            ),
            teacher_score=0.0 if item.id == "Q_NUM_01" else None,
        )
        for item in test.rubric.items
    ]
    grade = CopyGrade(
        copy_id="test-override",
        total_score=sum(q.score for q in questions),
        total_possible=20.0,
        questions=questions,
    )
    grade.compute_final_score()
    # Q_NUM_01 vaut 1.25 pt — refusé → 0, donc score = 20 - 1.25 = 18.75
    assert grade.final_score == pytest.approx(18.75)
