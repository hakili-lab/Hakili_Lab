"""Calcul de la tendance de progression d'un élève à partir de ses deux
dernières copies notées.

Même esprit que classe_normalizer.py / centre_normalizer.py : une constante
métier éditable à un seul endroit (SEUIL_TENDANCE) et une fonction pure,
testable indépendamment de l'interface et de la base — voir ces deux modules
pour le précédent déjà établi dans ce projet.
"""
from __future__ import annotations

from typing import Literal, Protocol

# Écart minimal (en points sur 20) entre les deux dernières notes pour
# considérer qu'un élève progresse ou régresse plutôt que stagne. SEUL
# endroit à modifier pour ajuster la sensibilité du code couleur.
SEUIL_TENDANCE: float = 1.0

Tendance = Literal["progresse", "stagne", "regresse", "insuffisant"]


class _CopieNotee(Protocol):
    """Ce dont calculer_tendance a besoin — n'importe quel objet avec ces
    deux attributs convient (Copie de src.db.models, ou un objet de test)."""
    notes_finales: float | None
    date_soumission: object  # comparable (date) — seul l'ordre relatif compte


def calculer_tendance(copies: list[_CopieNotee]) -> Tendance:
    """Détermine la tendance d'un élève à partir de l'historique de ses
    copies (ordre quelconque en entrée).

    Ne prend en compte que les copies avec notes_finales renseignée (une
    copie NULL est en cours de traitement, elle ne compte pas). Compare les
    DEUX plus récentes parmi celles-ci (triées par date_soumission).

    Retourne :
    - "insuffisant" : moins de 2 copies notées (0 ou 1) — cas gris, l'appelant
      doit quand même afficher l'élève, jamais le cacher.
    - "progresse"   : écart >= +SEUIL_TENDANCE
    - "regresse"    : écart <= -SEUIL_TENDANCE
    - "stagne"      : écart strictement entre les deux (dont écart nul)
    """
    notees = [c for c in copies if c.notes_finales is not None]
    if len(notees) < 2:
        return "insuffisant"

    notees_triees = sorted(notees, key=lambda c: c.date_soumission)
    avant_derniere, derniere = notees_triees[-2], notees_triees[-1]
    ecart = derniere.notes_finales - avant_derniere.notes_finales

    if ecart >= SEUIL_TENDANCE:
        return "progresse"
    if ecart <= -SEUIL_TENDANCE:
        return "regresse"
    return "stagne"
