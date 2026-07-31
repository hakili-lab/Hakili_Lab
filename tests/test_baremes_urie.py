"""
Tests des barèmes Urie v2 (data/knowledge/bareme_urie_*.yaml).

Ces fichiers sont générés par scripts/generer_baremes_urie.py depuis
Referentiel_Urie_v0.xlsx. Les tests ci-dessous verrouillent les propriétés qui
doivent tenir après toute régénération.

Le test le plus important est `test_copie_parfaite_vaut_exactement_20` : une
question de partie A vaut 1/3 de point, non représentable exactement en décimal
(30 × 0,333333 = 9,99999). C'est sans conséquence tant que la note se calcule
contre la somme réelle des max_score — mais un total déclaré utilisé comme
dénominateur ferait réapparaître le bug constaté sur les anciens barèmes, où une
copie parfaite valait 18,5/20. Voir docs/harmonisation_donnees.md §4 et §5.1.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_KB_DIR = Path(__file__).parent.parent / "data" / "knowledge"

_NIVEAUX = ("6eme", "5eme", "4eme", "3eme", "2ndeC", "1ereD", "tleD")

# Classe canonique attendue par test — doit être reconnue par normalize_classe,
# sinon resolve_classe refuse d'écrire la classe en base.
_CLASSE_ATTENDUE = {
    "6eme": "6e", "5eme": "5e", "4eme": "4e", "3eme": "3e",
    "2ndeC": "2nde", "1ereD": "1ere", "tleD": "Tle",
}

_TYPES_ERREUR = {"PRQ", "CPT", "MOD", "PRC", "CNS", "RED", "ATT"}
_FORMATS = {"qcm", "court", "redige", "construction"}


def _charger(niveau: str) -> dict:
    path = _KB_DIR / f"bareme_urie_{niveau}.yaml"
    assert path.exists(), f"{path.name} absent — lancer scripts/generer_baremes_urie.py"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("niveau", _NIVEAUX)
def test_40_questions_par_test(niveau: str) -> None:
    data = _charger(niveau)
    assert len(data["questions"]) == 40
    assert data["meta"]["total_questions"] == 40


@pytest.mark.parametrize("niveau", _NIVEAUX)
def test_structure_partie_a_et_b(niveau: str) -> None:
    """30 questions courtes en partie A, 10 exercices rédigés en partie B."""
    qs = _charger(niveau)["questions"]
    assert sum(1 for q in qs if q["partie"] == "A") == 30
    assert sum(1 for q in qs if q["partie"] == "B") == 10


@pytest.mark.parametrize("niveau", _NIVEAUX)
def test_bareme_sur_20(niveau: str) -> None:
    """Décision D-CEO-26 : barème stocké sur 20, converti du classeur (/60) par 3."""
    data = _charger(niveau)
    assert data["meta"]["bareme_classeur_total"] == pytest.approx(60.0)
    assert sum(q["bareme"] for q in data["questions"]) == pytest.approx(20.0, abs=1e-4)
    for q in data["questions"]:
        assert q["bareme"] == pytest.approx(q["bareme_classeur"] / 3, abs=1e-6)


@pytest.mark.parametrize("niveau", _NIVEAUX)
def test_classe_reconnue_par_le_normaliseur(niveau: str) -> None:
    """`meta.classe` alimente HakiliTest.niveaux, que resolve_classe utilise comme
    garde-fou : une valeur non reconnue empêcherait d'écrire la classe en base."""
    from src.core.classe_normalizer import normalize_classe

    classe = _charger(niveau)["meta"]["classe"]
    assert classe == _CLASSE_ATTENDUE[niveau]
    assert normalize_classe(classe) == classe


@pytest.mark.parametrize("niveau", _NIVEAUX)
def test_codes_uniques_et_champs_valides(niveau: str) -> None:
    qs = _charger(niveau)["questions"]
    codes = [q["code"] for q in qs]
    assert len(set(codes)) == len(codes), "codes de question dupliqués"
    for q in qs:
        assert q["format"] in _FORMATS, f"{q['code']} : format inconnu {q['format']!r}"
        assert q["competence"], f"{q['code']} : compétence manquante"
        assert q["objet"], f"{q['code']} : intitulé manquant"


@pytest.mark.parametrize("niveau", _NIVEAUX)
def test_qcm_ont_leur_bonne_reponse(niveau: str) -> None:
    """Les QCM sont corrigeables sans appel LLM : une lettre cochée suffit."""
    for q in _charger(niveau)["questions"]:
        if q["format"] != "qcm":
            continue
        options = q.get("options") or []
        assert options, f"{q['code']} : QCM sans options"
        correctes = [o for o in options if o["correcte"]]
        assert len(correctes) == 1, f"{q['code']} : {len(correctes)} bonnes réponses"
        assert q["reponse_attendue"] == correctes[0]["lettre"]


@pytest.mark.parametrize("niveau", _NIVEAUX)
def test_distracteurs_tagues_par_un_type_ferme(niveau: str) -> None:
    """Chaque mauvaise option porte un type d'erreur de la liste fermée — c'est ce
    qui permet au module 4 de diagnostiquer un QCM sans interprétation."""
    for q in _charger(niveau)["questions"]:
        for o in q.get("options") or []:
            if o["correcte"]:
                continue
            assert o.get("type_erreur") in _TYPES_ERREUR, (
                f"{q['code']} option {o['lettre']} : type {o.get('type_erreur')!r} "
                "hors de la liste fermée"
            )


def test_corriges_manquants_uniquement_hors_qcm() -> None:
    """Arbitrage B non tranché : 209 questions sans corrigé, et ce sont exactement
    les non-QCM. Ce test échouera dès qu'un corrigé sera ajouté — c'est voulu :
    il faudra alors mettre à jour le compte, ce qui documente la progression."""
    sans_corrige = sum(
        1
        for niveau in _NIVEAUX
        for q in _charger(niveau)["questions"]
        if not q["reponse_attendue"]
    )
    non_qcm = sum(
        1
        for niveau in _NIVEAUX
        for q in _charger(niveau)["questions"]
        if q["format"] != "qcm"
    )
    assert sans_corrige == non_qcm == 209


# ── Le test central : la note d'une copie parfaite ────────────────────────────

@pytest.mark.parametrize("niveau", _NIVEAUX)
def test_copie_parfaite_vaut_exactement_20(niveau: str) -> None:
    from src.knowledge.test_registry import get_registry
    from src.models.domain import CopyGrade, QuestionGrade, TeacherDecision

    test = get_registry().get_test(f"urie_{niveau}")
    assert test is not None

    questions = [
        QuestionGrade(
            rubric_item_id=item.id,
            score=item.max_score,
            confidence=1.0,
            comment="",
            observed_answer="",
            requires_review=False,
            teacher_decision=TeacherDecision.accepted,
        )
        for item in test.rubric.items
    ]
    grade = CopyGrade(
        copy_id="test",
        total_score=sum(i.max_score for i in test.rubric.items),
        total_possible=test.rubric.total_points,
        questions=questions,
    ).compute_final_score()

    assert grade.final_score_on_20 == pytest.approx(20.0)


@pytest.mark.parametrize("niveau", _NIVEAUX)
def test_copie_nulle_vaut_zero(niveau: str) -> None:
    from src.knowledge.test_registry import get_registry
    from src.models.domain import CopyGrade, QuestionGrade, TeacherDecision

    test = get_registry().get_test(f"urie_{niveau}")
    questions = [
        QuestionGrade(
            rubric_item_id=item.id,
            score=0.0,
            confidence=1.0,
            comment="",
            observed_answer="",
            requires_review=False,
            teacher_decision=TeacherDecision.accepted,
        )
        for item in test.rubric.items
    ]
    grade = CopyGrade(
        copy_id="test",
        total_score=0.0,
        total_possible=test.rubric.total_points,
        questions=questions,
    ).compute_final_score()

    assert grade.final_score_on_20 == pytest.approx(0.0)


# ── Registre : actifs vs archivés ─────────────────────────────────────────────

def test_les_7_tests_urie_sont_proposes() -> None:
    from src.knowledge.test_registry import get_registry

    disponibles = get_registry().available_tests()
    for niveau in _NIVEAUX:
        assert f"urie_{niveau}" in disponibles


def test_anciens_tests_archives_mais_toujours_resolus() -> None:
    """D-CEO-26 : masqués de la sélection, mais get_test() doit continuer à les
    résoudre — pipeline.py s'en sert pour la classe des copies déjà corrigées."""
    from src.knowledge.test_registry import get_registry

    registry = get_registry()
    anciens = [
        "hakili_3e_v1", "hakili_3e_v2", "hakili_6e_v1",
        "hakili_2ndeC_v1", "hakili_4e_v1", "hakili_tle_v1",
    ]
    for test_id in anciens:
        assert test_id not in registry.available_tests(), f"{test_id} encore proposé"
        test = registry.get_test(test_id)
        assert test is not None, f"{test_id} plus résolvable — casse l'historique"
        assert test.archive is True
        assert test.niveaux, f"{test_id} : niveaux perdus, résolution de classe cassée"
