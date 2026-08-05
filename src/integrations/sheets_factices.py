"""Jeu d'élèves et de personnel FACTICES — développement uniquement.

Pourquoi ce module existe
-------------------------
L'identité (élèves, personnel) vit dans les Google Sheets du docteur et nulle
part ailleurs (D-CEO-20/21/25). Sur une machine de développement, les
identifiants de Sheet ne sont pas renseignés : `get_eleves()` et
`get_personnel()` échouent, et **cinq écrans sur sept affichent
« momentanément indisponible »** — impossible d'y travailler la mise en page,
impossible de se connecter, impossible de voir un parcours.

Ce module fournit de quoi remplir ces écrans sans toucher aux Sheets réels.

Ce que ce module N'EST PAS
--------------------------
**Ce n'est pas une deuxième source de vérité.** La discipline du projet a déjà
démoli deux fois une table `eleve` en base (D-CEO-20, D-CEO-21) : le défaut
d'une deuxième source n'est pas qu'elle existe, c'est qu'elle *diverge en
silence* de la première. Trois propriétés l'en empêchent ici :

1. **Rien n'est écrit.** Ce module ne rend que des lignes en mémoire. Aucune
   table, aucune migration, aucun fichier.
2. **Il est inatteignable en production.** Il faut `HAKILI_SHEETS_FACTICES` ET
   `DEBUG` ; hors `DEBUG` le réglage est ignoré et l'oubli journalisé
   bruyamment, comme `HAKILI_ACCES_LIBRE` (`hakili/settings.py`).
3. **Il se branche à la place de la lecture réseau, pas à la place de la
   logique.** Il rend des lignes brutes avec les **en-têtes réels du Sheet** —
   `"Contact Parents"`, `"Prenom"`, `"Role"`… Tout l'aval s'exécute pour de
   vrai : résolution tolérante des colonnes, construction de
   `identifiant_hakili`, normalisation des classes, dérivation des centres,
   vérification du PIN. Un écran qui marche sur ces données marche sur les
   vraies ; et une régression dans cette chaîne se voit ici aussi.

Les noms sont inventés. Les numéros de téléphone sont dans la plage
documentaire `70 00 00 xx` et n'appartiennent à personne.

Usage
-----
    $env:DEBUG="true"; $env:HAKILI_SHEETS_FACTICES="true"; python manage.py runserver
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Identifiants de Sheet réservés, reconnus par `actif()` — ils ne désignent
# aucun classeur réel. Renseigner ces valeurs dans `.env` revient à demander le
# jeu factice, ce qui donne un second chemin d'activation plus explicite que la
# variable booléenne quand on veut ne simuler QU'UNE des deux sources.
SHEET_ELEVES_FACTICE = "FACTICE_ELEVES"
SHEET_PERSONNEL_FACTICE = "FACTICE_PERSONNEL"

_VRAI = {"1", "true", "yes", "on", "oui"}


def _bool_env(nom: str) -> bool:
    return os.environ.get(nom, "").strip().lower() in _VRAI


def actif() -> bool:
    """Vrai si le jeu factice doit remplacer la lecture des Sheets.

    Verrouillé sur `DEBUG`, délibérément et pour la même raison que
    `HAKILI_ACCES_LIBRE` : servir des élèves inventés à un enseignant qui croit
    consulter sa classe serait pire qu'un écran en panne — l'écran en panne, on
    le signale ; des données plausibles mais fausses, on les recopie.
    """
    demande = _bool_env("HAKILI_SHEETS_FACTICES")
    if not demande:
        return False

    if not _bool_env("DEBUG"):
        logger.error(
            "HAKILI_SHEETS_FACTICES est demandé hors DEBUG : IGNORÉ. Ce réglage "
            "remplacerait les élèves réels par un jeu inventé sans que l'écran le "
            "dise. Retirez-le de l'environnement de production."
        )
        return False

    return True


# ── Élèves ───────────────────────────────────────────────────────────────────
# En-têtes RÉELS du Sheet élèves (voir _COLONNES_ELEVES). Ne pas les traduire
# en noms logiques : c'est justement la résolution des colonnes qu'on veut voir
# s'exécuter.
#
# La couverture est choisie pour que les écrans montrent leurs cas limites, pas
# seulement leur cas nominal :
#   - les 7 niveaux de la 6ème à la Tle D, pour que le filtre par classe ait de
#     quoi trier ;
#   - trois centres, dont un vu une seule fois (Ouahigouya) — c'est le cas
#     « centre suspect » de `deriver_centres()`, qui doit être signalé sans
#     jamais être bloqué ;
#   - deux frères et sœurs au même contact (SAWADOGO), qui vérifient que
#     `build_identifiant_hakili` les distingue bien par le prénom ;
#   - un redoublant et une boursière, pour les colonnes rarement remplies.
_ELEVES: list[dict[str, Any]] = [
    {
        "Nom": "OUEDRAOGO", "Prenom": "Aminata", "Classe": "6e",
        "Centre": "Ouagadougou", "Ecole": "Lycée Bogodogo",
        "Reprend la classe?": "Non", "Boursier": "Oui",
        "Contact Parents": "70 00 00 01",
    },
    {
        "Nom": "SAWADOGO", "Prenom": "Boukary", "Classe": "6e",
        "Centre": "Ouagadougou", "Ecole": "Lycée Bogodogo",
        "Reprend la classe?": "Non", "Boursier": "Non",
        "Contact Parents": "70 00 00 02",
    },
    {
        "Nom": "SAWADOGO", "Prenom": "Fatimata", "Classe": "4e",
        "Centre": "Ouagadougou", "Ecole": "Lycée Bogodogo",
        "Reprend la classe?": "Non", "Boursier": "Non",
        "Contact Parents": "70 00 00 02",
    },
    {
        "Nom": "KABORE", "Prenom": "Salif", "Classe": "5e",
        "Centre": "Ouagadougou", "Ecole": "CEG Tanghin",
        "Reprend la classe?": "Oui", "Boursier": "Non",
        "Contact Parents": "70 00 00 03",
    },
    {
        "Nom": "ZONGO", "Prenom": "Mariam", "Classe": "5e",
        "Centre": "Bobo-Dioulasso", "Ecole": "Lycée Ouezzin Coulibaly",
        "Reprend la classe?": "Non", "Boursier": "Oui",
        "Contact Parents": "70 00 00 04",
    },
    {
        "Nom": "COMPAORE", "Prenom": "Issa", "Classe": "4e",
        "Centre": "Bobo-Dioulasso", "Ecole": "Lycée Ouezzin Coulibaly",
        "Reprend la classe?": "Non", "Boursier": "Non",
        "Contact Parents": "70 00 00 05",
    },
    {
        "Nom": "TRAORE", "Prenom": "Adama", "Classe": "3e",
        "Centre": "Ouagadougou", "Ecole": "CEG Tanghin",
        "Reprend la classe?": "Non", "Boursier": "Non",
        "Contact Parents": "70 00 00 06",
    },
    {
        "Nom": "NIKIEMA", "Prenom": "Clarisse", "Classe": "3e",
        "Centre": "Bobo-Dioulasso", "Ecole": "Lycée Ouezzin Coulibaly",
        "Reprend la classe?": "Non", "Boursier": "Non",
        "Contact Parents": "70 00 00 07",
    },
    {
        "Nom": "BANCE", "Prenom": "Yacouba", "Classe": "3e",
        "Centre": "Ouahigouya", "Ecole": "Lycée provincial",
        "Reprend la classe?": "Oui", "Boursier": "Non",
        "Contact Parents": "70 00 00 08",
    },
    {
        "Nom": "DIALLO", "Prenom": "Ramata", "Classe": "2nde C",
        "Centre": "Ouagadougou", "Ecole": "Lycée Bogodogo",
        "Reprend la classe?": "Non", "Boursier": "Oui",
        "Contact Parents": "70 00 00 09",
    },
    {
        "Nom": "SORE", "Prenom": "Moussa", "Classe": "1ere D",
        "Centre": "Ouagadougou", "Ecole": "Lycée Bogodogo",
        "Reprend la classe?": "Non", "Boursier": "Non",
        "Contact Parents": "70 00 00 10",
    },
    {
        "Nom": "ILBOUDO", "Prenom": "Awa", "Classe": "TleD",
        "Centre": "Bobo-Dioulasso", "Ecole": "Lycée Ouezzin Coulibaly",
        "Reprend la classe?": "Non", "Boursier": "Non",
        "Contact Parents": "70 00 00 11",
    },
]

# ── Personnel ────────────────────────────────────────────────────────────────
# Le Sheet réel a une ligne par AFFECTATION, pas par personne : KONE apparaît
# deux fois (deux centres). `_load_personnel` doit les regrouper en une seule
# personne — sans cette ligne en double, le regroupement ne serait jamais
# exercé en développement.
#
# Les PIN sont volontairement triviaux et tous distincts : ce sont des comptes
# de démonstration qui n'ouvrent rien de réel.
_PERSONNEL: list[dict[str, Any]] = [
    {
        "Nom": "OUATTARA", "Prenom": "Salimata", "Role": "administrateur",
        "Centre": "Ouagadougou", "classe": "", "PIN": "1000",
        "Email": "admin@example.invalid",
    },
    {
        "Nom": "SANOU", "Prenom": "Karim", "Role": "responsable",
        "Centre": "Bobo-Dioulasso", "classe": "", "PIN": "2000",
        "Email": "",
    },
    {
        "Nom": "KONE", "Prenom": "Bintou", "Role": "enseignant",
        "Centre": "Ouagadougou", "classe": "3e", "PIN": "3000",
        "Email": "",
    },
    {
        "Nom": "KONE", "Prenom": "Bintou", "Role": "enseignant",
        "Centre": "Bobo-Dioulasso", "classe": "4e", "PIN": "3000",
        "Email": "",
    },
    {
        "Nom": "TAPSOBA", "Prenom": "Ousmane", "Role": "enseignant",
        "Centre": "Ouagadougou", "classe": "6e", "PIN": "4000",
        "Email": "",
    },
    {
        "Nom": "ZOUNGRANA", "Prenom": "Alice", "Role": "enseignant",
        "Centre": "Ouahigouya", "classe": "3e", "PIN": "5000",
        "Email": "",
    },
]


def lignes_brutes(sheet_id: str, label: str) -> list[dict[str, Any]] | None:
    """Lignes factices pour ce Sheet, ou `None` si ce module ne le couvre pas.

    `None` — et non une liste vide — pour que l'appelant distingue « je ne sais
    pas répondre » de « ce Sheet est vide ». Une liste vide rendue par erreur
    afficherait « aucun élève » au lieu de la panne de configuration.

    Le tri se fait sur `label` (« élèves » / « personnel »), le nom logique que
    `_fetch_raw_rows` reçoit déjà, plutôt que sur `sheet_id` qui peut être vide
    en développement — c'est justement le cas qu'on vient couvrir.
    """
    if label.startswith("élève") or sheet_id == SHEET_ELEVES_FACTICE:
        return [dict(ligne) for ligne in _ELEVES]
    if label.startswith("personnel") or sheet_id == SHEET_PERSONNEL_FACTICE:
        return [dict(ligne) for ligne in _PERSONNEL]
    return None


def comptes_demonstration() -> list[tuple[str, str, str]]:
    """(nom complet, rôle, PIN) — de quoi afficher les identifiants sur l'écran
    de connexion en développement. Sans ça, le jeu factice serait inutilisable :
    on ne peut pas deviner un PIN."""
    return [
        (f"{p['Nom']} {p['Prenom']}", str(p["Role"]), str(p["PIN"]))
        for p in {(p["Nom"], p["Prenom"]): p for p in _PERSONNEL}.values()
    ]
