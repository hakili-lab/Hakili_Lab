"""
Rôles, casquettes, recherche par nom, nommage des documents.

Extrait de `src/ui/app.py` lors de la migration vers Django : ces fonctions
n'affichent rien, elles décident. Les laisser dans un fichier Streamlit de
2 876 lignes les rendait intestables et les aurait fait disparaître avec lui.
Aucune logique n'a été modifiée au passage — seulement déplacée et couverte de
tests.

Ce module ne dépend d'aucun framework : ni Streamlit, ni Django.
"""
from __future__ import annotations

import re
import unicodedata

from src.db.models import UserRole

# ── Rôles et casquettes ───────────────────────────────────────────────────────

ROLES_VALIDES = {r.value for r in UserRole}

LIBELLES_CASQUETTE = {
    UserRole.responsable_centre.value: "Responsable",
    UserRole.enseignant.value: "Enseignant",
    UserRole.admin.value: "Administrateur",
}


def roles_valides_de(personne: dict) -> list[str]:
    """Rôles reconnus d'une personne du Sheet personnel.

    Lit `personne["roles"]` (double rôle possible) avec repli sur
    `personne["role"]`. Un rôle du Sheet non reconnu par `UserRole` est ignoré
    plutôt que de faire planter l'aiguillage — l'erreur claire est montrée à la
    connexion, pas ici.
    """
    roles = personne.get("roles") or ([personne["role"]] if personne.get("role") else [])
    return [r for r in roles if r in ROLES_VALIDES]


def vue_utilisateur_pour_casquette(personne: dict, casquette: str) -> dict:
    """Construit le dict utilisateur attendu par les vues.

    Ne pose plus que `role_enum`. Les affectations (centre, classe) sont
    conservées telles quelles, à titre informatif : elles ne commandent plus
    l'accès aux élèves depuis que le périmètre est unique (centre d'encadrement,
    pas école — voir `src/services/user_service.py`).
    """
    vue = dict(personne)
    vue["role_enum"] = UserRole(casquette)
    return vue


def casquette_par_defaut(roles: list[str]) -> str:
    """Administrateur si la personne l'est, sinon son premier rôle reconnu.

    Depuis que le périmètre élève ne dépend plus du rôle (centre d'encadrement,
    pas école — voir `src/services/user_service.py`), le rôle ne commande plus
    qu'une chose : l'accès à l'administration. Choisir autre chose qu'admin pour
    quelqu'un qui l'est reviendrait à lui cacher ses propres écrans.
    """
    if UserRole.admin.value in roles:
        return UserRole.admin.value
    return roles[0] if roles else ""


# ── Repliage et recherche ─────────────────────────────────────────────────────

def fold_token(text: str) -> str:
    """Minuscule, sans accents, lettres et chiffres uniquement — pour comparer
    sans se soucier de la casse, des accents ni du séparateur."""
    normalized = unicodedata.normalize("NFD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]", "", ascii_text)


def fold_texte(text: str) -> str:
    """Comme `fold_token` mais conserve un espace entre les mots — base d'une
    recherche insensible à l'**ordre** des mots : « Sanou Feryel » doit retrouver
    « Feryel SANOU » même si l'affichage montre le prénom en premier."""
    normalized = unicodedata.normalize("NFD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()


def correspond_recherche(requete: str, cible: str) -> bool:
    """Vrai si chaque mot de `requete` apparaît dans `cible`, ordre ignoré,
    insensible à la casse et aux accents. Une requête vide correspond toujours."""
    mots = fold_texte(requete).split()
    cible_repliee = fold_texte(cible)
    return all(mot in cible_repliee for mot in mots)


def filtrer_par_recherche(items: list[dict], requete: str, format_func) -> list[dict]:
    """Filtre une liste de personnes ou d'élèves sur le libellé affiché."""
    if not requete or not requete.strip():
        return list(items)
    return [item for item in items if correspond_recherche(requete, format_func(item))]


# ── Nommage des documents ─────────────────────────────────────────────────────

def _nettoyer_pour_nom_fichier(text: str) -> str:
    """Retire accents, espaces, apostrophes et tout caractère non alphanumérique
    — pour rester un nom de fichier valide sous Windows comme sous Linux."""
    normalized = unicodedata.normalize("NFD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9]+", "_", ascii_text).strip("_")


def nom_fichier_document(*, nom: str, prenom: str, doc_type: str, date) -> str:
    """Nom lisible pour un document téléchargé : NOM_Prenom_type_date, sans
    extension.

    Ne contient **jamais** `contact_parents` — le numéro du parent ne doit pas
    voyager dans des fichiers qui circulent par WhatsApp ou par mail — ni
    `identifiant_hakili`. Seulement nom et prénom, comme affichés à l'écran.

    À appliquer partout où un document est proposé au téléchargement.
    """
    nom_c = _nettoyer_pour_nom_fichier(nom).upper()
    prenom_c = _nettoyer_pour_nom_fichier(prenom)
    parts = [p for p in (nom_c, prenom_c) if p]
    base = "_".join(parts) if parts else "eleve"
    return f"{base}_{doc_type}_{date}"


# ── Appariement fichier ↔ élève (mode batch) ─────────────────────────────────

def apparier_eleve_par_nom_fichier(nom_fichier: str, eleves: list[dict]) -> dict | None:
    """Fait correspondre un fichier déposé (nommé par convention avec le nom et
    le prénom de l'élève) à un élève des Sheets.

    Une sélection manuelle par fichier n'a pas de sens pour trente copies d'un
    coup, mais deviner serait pire : l'élève n'est retourné que si son nom **et**
    son prénom apparaissent dans le nom de fichier et qu'un seul élève
    correspond. Sinon `None` — introuvable ou ambigu — et l'appelant doit bloquer
    cette copie plutôt que d'attribuer au hasard.
    """
    tokens_fichier = {fold_token(t) for t in re.split(r"[_\-\s]+", nom_fichier) if t}
    correspondances = [
        eleve
        for eleve in eleves
        if (tokens := {fold_token(eleve.get("nom", "")), fold_token(eleve.get("prenom", ""))})
        and all(tokens)
        and tokens <= tokens_fichier
    ]
    return correspondances[0] if len(correspondances) == 1 else None
