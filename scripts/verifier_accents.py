"""
Audit des accents manquants dans Referentiel_Socle_v0.xlsx.

Le problème
-----------
Le classeur est incohérent avec lui-même : le même mot y apparaît tantôt accentué,
tantôt non — « apres » 34 fois contre « après » 36 fois, « carre » 29 fois contre
« carré » 10 fois. Ce ne sont donc pas des saisies volontairement sans accents,
mais des oublis. Ces textes servent de libellés de question dans l'interface et
seront lus par des enseignants et des parents.

Pourquoi ce script AUDITE au lieu de CORRIGER
---------------------------------------------
Une correction automatique introduirait du faux français. Pour beaucoup de ces
mots, la forme sans accent est elle-même un mot français valide, et seule
l'intention de l'auteur tranche :

    « calcule »  -> « calcule » (je calcule) ou « calculé » (participe) ?
    « applique » -> « applique » ou « appliqué » ?
    « cote »     -> « côté » (géométrie), « côte », « coté », ou « cote » (dimension) ?
    « eleve »    -> « élève » (l'apprenant) ou « élevé » (au carré) ?

Un remplacement à l'aveugle depuis la seule forme repliée écrirait « élevé au
carré » là où il fallait « élève », et personne ne s'en apercevrait. La règle du
projet — ne jamais deviner une donnée — s'applique ici comme ailleurs.

La correction se fait donc À LA SOURCE, dans le classeur, par la personne qui en
a la charge. Ce script produit la liste exacte à corriger. Le classeur doit de
toute façon être relu par un enseignant de mathématiques avant figeage
(`00_Notice` : « À VALIDER ») : c'est le même passage.

Ce que garantit le dispositif
-----------------------------
`tests/test_accents_referentiel.py` verrouille le compte actuel. Si une mise à
jour du classeur introduit de nouveaux mots non accentués, le test échoue au lieu
de laisser la qualité se dégrader en silence — même logique que le garde-fou sur
les `chunk_ids` cassés, qui eux étaient journalisés en `debug` et donc invisibles.

Usage :
    python scripts/verifier_accents.py            # rapport à l'écran
    python scripts/verifier_accents.py --rapport  # + docs/accents_a_corriger.md
"""
from __future__ import annotations

import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

_ROOT = Path(__file__).resolve().parent.parent
_CLASSEUR_CANDIDATS = [
    _ROOT.parent / "Referentiel_Socle_v0.xlsx",
    _ROOT / "Referentiel_Socle_v0.xlsx",
]

# Colonnes destinées à être lues par un humain, par onglet.
_COLONNES_LISIBLES: dict[str, list[int]] = {
    "02_Competences": [2, 3],          # libellé, description
    "04_Questions": [8],               # objet de la question
    "05_Grille_diagnostic": [4, 5],    # ce qu'on lit sur la copie, lacune révélée
    "06_Distracteurs": [3, 6],         # texte de l'option, erreur qui y conduit
}

# Mots dont la forme sans accent est AUSSI un mot français valide : seule
# l'intention de l'auteur tranche, aucune correction ne peut être déduite.
# Listés à part pour que le rapport les signale comme « à arbitrer » plutôt que
# comme « à corriger ».
_HOMOGRAPHES = {
    "a", "ou", "la", "des", "du", "sur", "mur", "cote", "cotes", "cotee",
    "eleve", "eleves", "pres", "ete", "tache", "taches", "mode", "pale",
    "cru", "pu", "ca", "entre", "marche", "colle", "jeune", "foret",
    # formes verbales : « je calcule » vs « calculé »
    "calcule", "applique", "divise", "multiplie", "developpe", "decompose",
    "distribue", "change", "determine", "simplifie", "reduit", "compare",
    "place", "trace", "compte", "note", "pose", "donne", "trouve", "ajoute",
}


def _fold(mot: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", mot) if not unicodedata.combining(c)
    )


def _trouver_classeur() -> Path:
    for p in _CLASSEUR_CANDIDATS:
        if p.exists():
            return p
    raise SystemExit("Referentiel_Socle_v0.xlsx introuvable.")


def _collecter(chemin: Path) -> tuple[Counter, dict[str, set[str]]]:
    """Retourne (compte des mots, mot -> onglets où il apparaît)."""
    wb = openpyxl.load_workbook(chemin, data_only=True, read_only=True)
    mots: Counter = Counter()
    emplacements: dict[str, set[str]] = defaultdict(set)

    for onglet, colonnes in _COLONNES_LISIBLES.items():
        for ligne in list(wb[onglet].iter_rows(values_only=True))[1:]:
            for col in colonnes:
                if col >= len(ligne) or ligne[col] is None:
                    continue
                for mot in re.findall(r"[A-Za-zÀ-ÿ']+", str(ligne[col])):
                    bas = mot.lower()
                    mots[bas] += 1
                    emplacements[bas].add(onglet)
    wb.close()
    return mots, emplacements


def analyser(chemin: Path) -> dict:
    mots, emplacements = _collecter(chemin)

    accentues = {m for m in mots if any(ord(c) > 127 for c in m)}
    # Forme repliée -> forme accentuée attestée dans le classeur lui-même.
    attestees: dict[str, str] = {_fold(m): m for m in accentues}

    a_corriger: list[dict] = []
    a_arbitrer: list[dict] = []
    for mot in sorted(mots):
        if any(ord(c) > 127 for c in mot) or mot not in attestees:
            continue
        entree = {
            "mot": mot,
            "suggestion": attestees[mot],
            "occurrences_sans": mots[mot],
            "occurrences_avec": mots[attestees[mot]],
            "onglets": sorted(emplacements[mot]),
        }
        (a_arbitrer if mot in _HOMOGRAPHES else a_corriger).append(entree)

    return {
        "mots_distincts": len(mots),
        "mots_accentues": len(accentues),
        "a_corriger": a_corriger,
        "a_arbitrer": a_arbitrer,
    }


def _ecrire_rapport(res: dict, chemin_classeur: Path) -> Path:
    sortie = _ROOT / "docs" / "accents_a_corriger.md"
    lignes = [
        "# Accents à corriger dans `Referentiel_Socle_v0.xlsx`",
        "",
        "**Généré par `scripts/verifier_accents.py`** — ne pas éditer à la main, relancer le script.",
        f"**Source :** `{chemin_classeur.name}`",
        "",
        "Ces textes servent de libellés de question dans l'interface et apparaissent",
        "dans les rapports lus par les enseignants et les parents. La correction se fait",
        "**dans le classeur**, pas dans le code : voir le docstring du script pour le motif.",
        "",
        "Chaque mot ci-dessous est écrit **sans accent** à certains endroits alors que sa",
        "forme accentuée existe **ailleurs dans le même classeur** — c'est donc un oubli,",
        "pas un choix.",
        "",
        f"## À corriger — {len(res['a_corriger'])} mots",
        "",
        "La forme accentuée ne fait aucun doute.",
        "",
        "| Mot écrit | Corriger en | Occurrences sans | Déjà correct ailleurs | Onglets |",
        "|---|---|---|---|---|",
    ]
    for e in res["a_corriger"]:
        lignes.append(
            f"| `{e['mot']}` | **{e['suggestion']}** | {e['occurrences_sans']} | "
            f"{e['occurrences_avec']} | {', '.join(e['onglets'])} |"
        )

    lignes += [
        "",
        f"## À arbitrer — {len(res['a_arbitrer'])} mots",
        "",
        "Pour ces mots, la forme **sans** accent est aussi un mot français valide :",
        "seule l'intention de l'auteur tranche. À relire dans leur contexte, une par une.",
        "Exemples du piège : « calcule » (je calcule) ou « calculé » ? « eleve » (l'élève)",
        "ou « élevé » au carré ? « cote » : côté, côte, coté, ou cote (dimension) ?",
        "",
        "| Mot écrit | Lecture possible | Occurrences sans | Onglets |",
        "|---|---|---|---|",
    ]
    for e in res["a_arbitrer"]:
        lignes.append(
            f"| `{e['mot']}` | {e['suggestion']} ? | {e['occurrences_sans']} | "
            f"{', '.join(e['onglets'])} |"
        )

    lignes += [
        "",
        "## Après correction",
        "",
        "1. Relancer `python scripts/verifier_accents.py` — les deux listes doivent se vider.",
        "2. Régénérer les barèmes : `python scripts/generer_baremes_socle.py`",
        "   (⚠ sauvegarder d'abord les corrigés saisis à la main — la régénération les écrase).",
        "3. Mettre à jour le compte attendu dans `tests/test_accents_referentiel.py`.",
        "",
    ]
    sortie.write_text("\n".join(lignes), encoding="utf-8")
    return sortie


def main() -> int:
    chemin = _trouver_classeur()
    res = analyser(chemin)

    print(f"Classeur : {chemin}\n")
    print(f"  Mots distincts dans les textes lisibles : {res['mots_distincts']}")
    print(f"  dont écrits avec accents                : {res['mots_accentues']}")
    print()
    print(f"  À CORRIGER (forme accentuée certaine)   : {len(res['a_corriger'])} mots")
    print(f"  À ARBITRER (homographes, ambigus)       : {len(res['a_arbitrer'])} mots")
    print()

    apercu = res["a_corriger"][:12]
    if apercu:
        print("  Aperçu des corrections :")
        for e in apercu:
            print(
                f"    {e['mot']:20s} -> {e['suggestion']:22s} "
                f"({e['occurrences_sans']}x sans, {e['occurrences_avec']}x déjà correct)"
            )
        if len(res["a_corriger"]) > len(apercu):
            print(f"    … et {len(res['a_corriger']) - len(apercu)} autres")

    if "--rapport" in sys.argv:
        sortie = _ecrire_rapport(res, chemin)
        print(f"\n  Rapport complet écrit : {sortie.relative_to(_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
