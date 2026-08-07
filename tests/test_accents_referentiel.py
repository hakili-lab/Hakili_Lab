"""
Garde-fou sur les accents du référentiel.

Ce test ne corrige rien : il empêche la situation de s'aggraver en silence.

Le classeur contient aujourd'hui des mots écrits sans accent alors que leur forme
accentuée existe ailleurs dans le même fichier (« apres » 34x contre « après »
36x). Ces textes deviennent des libellés de question dans l'interface et des
lignes dans les rapports lus par les enseignants et les parents.

La correction se fait à la source, dans le classeur — voir
`scripts/verifier_accents.py` pour le motif (une correction automatique
introduirait du faux français : « calcule » ou « calculé » ?) et
`docs/accents_a_corriger.md` pour la liste à corriger.

Ce que ce test garantit : si une mise à jour du classeur **ajoute** de nouveaux
mots non accentués, la suite de tests échoue. Sans lui, la qualité se dégraderait
sans que personne le voie — exactement le défaut des `chunk_ids` cassés de
l'ancien système, journalisés en `logger.debug` donc invisibles en exploitation.

Quand le classeur est corrigé, faire baisser les deux plafonds ci-dessous. Ils ne
doivent jamais remonter.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent
_SCRIPT = _ROOT / "scripts" / "verifier_accents.py"

# Plafonds constatés le 2026-07-30, avant toute correction du classeur.
# À faire BAISSER au fur et à mesure des corrections, jamais monter.
_MAX_A_CORRIGER = 150
_MAX_A_ARBITRER = 16


def _charger_script():
    spec = importlib.util.spec_from_file_location("verifier_accents", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def resultat():
    if not _SCRIPT.exists():
        pytest.skip("scripts/verifier_accents.py absent")
    module = _charger_script()
    try:
        chemin = module._trouver_classeur()
    except SystemExit:
        pytest.skip("Referentiel_Socle_v0.xlsx introuvable — audit impossible")
    return module.analyser(chemin)


def test_pas_de_nouveaux_mots_sans_accent(resultat) -> None:
    """Le nombre de mots à corriger ne doit jamais augmenter."""
    n = len(resultat["a_corriger"])
    assert n <= _MAX_A_CORRIGER, (
        f"{n} mots sans accent (plafond {_MAX_A_CORRIGER}) — le classeur a régressé. "
        f"Lancer : python scripts/verifier_accents.py --rapport"
    )


def test_pas_de_nouveaux_homographes_ambigus(resultat) -> None:
    n = len(resultat["a_arbitrer"])
    assert n <= _MAX_A_ARBITRER, (
        f"{n} mots ambigus (plafond {_MAX_A_ARBITRER}) — le classeur a régressé. "
        f"Lancer : python scripts/verifier_accents.py --rapport"
    )


def test_plafonds_a_jour(resultat) -> None:
    """Si le classeur a été corrigé, les plafonds doivent suivre — sinon le
    garde-fou se relâche et laisserait passer une régression future."""
    n_corr = len(resultat["a_corriger"])
    n_arb = len(resultat["a_arbitrer"])
    assert not (n_corr < _MAX_A_CORRIGER or n_arb < _MAX_A_ARBITRER), (
        f"Le classeur s'est amélioré ({n_corr} à corriger, {n_arb} à arbitrer) : "
        f"abaisser _MAX_A_CORRIGER à {n_corr} et _MAX_A_ARBITRER à {n_arb} "
        f"dans {Path(__file__).name}."
    )


def test_les_libelles_generes_restent_lisibles() -> None:
    """Contrôle de bout en bout : les intitulés arrivent bien dans les barèmes
    générés. Ne juge pas les accents — vérifie qu'aucun libellé n'est vide ni
    tronqué, ce qui serait le vrai défaut bloquant pour l'enseignant."""
    import yaml

    kb = _ROOT / "data" / "knowledge"
    fichiers = sorted(kb.glob("bareme_socle_*.yaml"))
    if not fichiers:
        pytest.skip("barèmes v2 non générés")

    for f in fichiers:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        for q in data["questions"]:
            libelle = q["objet"]
            assert libelle.strip(), f"{f.name}/{q['code']} : libellé vide"
            assert len(libelle) >= 10, f"{f.name}/{q['code']} : libellé suspect {libelle!r}"
