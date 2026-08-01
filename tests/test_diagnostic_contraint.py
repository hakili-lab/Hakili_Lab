"""
Schémas et outil du diagnostic contraint (module 4), côté indépendant du framework.

La validation métier des codes vit dans `referentiel/diagnostic.py` (Django, testé
dans `referentiel/tests_diagnostic.py`). Ici on protège la **première** des trois
barrières : le schéma de l'outil, qui déclare les codes admis en `enum` et rend un
code hors référentiel très difficile à produire plutôt que rattrapable après coup.
"""
from __future__ import annotations

from src.api.claude_client import _diagnostic_contraint_tool
from src.models.domain import (
    DiagnosticContraint,
    ProblemeDetecte,
    SortieDiagnosticContraint,
    SourceProbleme,
)


def _schema_probleme(outil: dict) -> dict:
    return outil["input_schema"]["properties"]["problemes"]["items"]["properties"]


def test_les_codes_admis_sont_des_enums() -> None:
    outil = _diagnostic_contraint_tool(["L5", "L7"], ["L.IDR", "L.DEV1"], ["CPT", "PRC"])
    champs = _schema_probleme(outil)
    assert champs["code_question"]["enum"] == ["L5", "L7"]
    assert champs["code_competence"]["enum"] == ["L.IDR", "L.DEV1"]
    assert champs["code_type_erreur"]["enum"] == ["CPT", "PRC"]


def test_les_quatre_champs_sont_obligatoires() -> None:
    """Une citation facultative viderait le diagnostic de ce qui le rend
    arbitrable face au corpus de référence."""
    outil = _diagnostic_contraint_tool(["L5"], ["L.IDR"], ["CPT"])
    requis = outil["input_schema"]["properties"]["problemes"]["items"]["required"]
    assert set(requis) == {
        "code_question", "code_competence", "code_type_erreur", "citation",
    }


def test_aucune_prose_dans_le_schema() -> None:
    """Le module 4 existe pour remplacer le texte libre : rien dans la sortie ne
    doit permettre d'en produire à nouveau."""
    outil = _diagnostic_contraint_tool(["L5"], ["L.IDR"], ["CPT"])
    proprietes = outil["input_schema"]["properties"]
    assert list(proprietes) == ["problemes"]


def test_sortie_du_modele_se_parse() -> None:
    sortie = SortieDiagnosticContraint.model_validate(
        {
            "problemes": [
                {
                    "code_question": "L7",
                    "code_competence": "L.IDR",
                    "code_type_erreur": "CPT",
                    "citation": "écrit (x-5)^2",
                }
            ]
        }
    )
    assert sortie.problemes[0].source == SourceProbleme.modele


def test_une_copie_est_valide_sans_rejet() -> None:
    """C'est l'unité que compte le jalon « 100 sorties consécutives valides »."""
    diagnostic = DiagnosticContraint(copy_id="C1", niveau_test="3eme")
    assert diagnostic.valide

    diagnostic.rejets.append("L7 : compétence 'L.FANTOME' non admise.")
    assert not diagnostic.valide


def test_un_probleme_qcm_se_distingue_dun_probleme_du_modele() -> None:
    """Sans la distinction, l'écart du module 4 serait flatté par les QCM, dont
    le diagnostic est mécanique et ne peut pas se tromper."""
    qcm = ProblemeDetecte(
        code_question="L5", code_competence="L.IDR", code_type_erreur="CPT",
        citation="option a cochée", source=SourceProbleme.qcm,
    )
    assert qcm.source is SourceProbleme.qcm
    assert qcm.source.value == "qcm"
