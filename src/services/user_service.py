"""Accès aux élèves.

Modèle d'accès — un centre d'encadrement, pas une école
-------------------------------------------------------
Hakili Lab est un **centre d'encadrement** : les enseignants n'ont pas « leurs »
classes au sens scolaire. Ils tournent, se remplacent, reprennent les copies d'un
collègue absent. Cloisonner par centre et par classe bloquait un travail
parfaitement légitime, sans rien protéger d'utile — une copie mal attribuée est
empêchée par la sélection explicite de l'élève (D-CEO-20), pas par le périmètre.

La règle est donc simple : **toute personne autorisée voit tous les élèves.**
L'autorisation, elle, se contrôle en amont — une personne présente dans le Sheet
du personnel avec un code d'accès peut travailler ; retirée, elle ne peut plus.
C'est là que se joue la sécurité, pas dans un filtrage par classe.

Le **rôle** reste distinct pour une seule chose : l'administration (statistiques,
référentiel, gestion des accès). Il ne détermine plus quels élèves sont visibles.

`user` est un dict issu du Sheet, enrichi de `role_enum` à la connexion — pas un
objet de base : il n'existe aucune table portant l'identité (D-CEO-20, D-CEO-21).
"""
from __future__ import annotations

from src.core.roles import UserRole


def get_accessible_eleves(user: dict) -> list[dict]:
    """Tous les élèves, pour toute personne autorisée.

    Le filtrage par centre et par classe a été retiré : voir le docstring du
    module. `user` est conservé en paramètre — la signature est appelée depuis
    plusieurs vues, et un rôle non reconnu ne doit rien renvoyer.
    """
    from src.integrations.google_sheets import get_eleves

    if not user or user.get("role_enum") not in set(UserRole):
        return []
    return get_eleves()


def can_access_eleve(db, user: dict, eleve: dict) -> bool:
    """Vrai pour toute personne autorisée.

    Même critère que `get_accessible_eleves` — les deux DOIVENT rester cohérents.
    Une divergence entre eux a déjà causé un bug par le passé : un enseignant se
    voyait refuser l'accès au profil d'un élève que la liste lui montrait pourtant.

    `db` n'est pas utilisé ; le paramètre est conservé parce que plusieurs
    appelants le passent encore.
    """
    return bool(user and user.get("role_enum") in set(UserRole) and eleve)


def est_administrateur(user: dict) -> bool:
    """Seule distinction de rôle qui subsiste : l'accès à l'administration."""
    return bool(user and user.get("role_enum") == UserRole.admin)
