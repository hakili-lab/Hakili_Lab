"""Calcul de la tendance de progression d'un élève à partir de ses deux
dernières copies notées.

Même esprit que classe_normalizer.py / centre_normalizer.py : une constante
métier éditable à un seul endroit (SEUIL_TENDANCE) et une fonction pure,
testable indépendamment de Streamlit et de la base — voir ces deux modules
pour le précédent déjà établi dans ce projet.
"""
from __future__ import annotations

from typing import Any, Literal, Protocol, Sequence

# Écart minimal (en points sur 20) entre les deux dernières notes pour
# considérer qu'un élève progresse ou régresse plutôt que stagne. SEUL
# endroit à modifier pour ajuster la sensibilité du code couleur.
SEUIL_TENDANCE: float = 1.0

Tendance = Literal["progresse", "stagne", "regresse", "insuffisant"]


class _Comparable(Protocol):
    """N'importe quel type ordonnable (date, datetime, ou un objet de test) —
    seul l'ordre relatif compte pour trier les copies par date_soumission."""
    def __lt__(self, other: Any) -> bool: ...


class _CopieNotee(Protocol):
    """Ce dont calculer_tendance a besoin — n'importe quel objet avec ces
    deux attributs convient (Copie de src.db.models, ou un objet de test).

    date_soumission déclaré comme propriété (pas un attribut simple) :
    la correspondance de Protocol sur un attribut de donnée est invariante
    (le type doit matcher exactement), alors qu'une propriété est covariante
    sur son type de retour — seule façon d'accepter aussi bien `date` que
    `datetime` ou un objet de test sans dupliquer le Protocol par type."""
    notes_finales: float | None

    @property
    def date_soumission(self) -> _Comparable: ...


def calculer_tendance(copies: Sequence[_CopieNotee]) -> Tendance:
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
    # Extrait (date, note) dès le filtrage : la garde "notes_finales is not
    # None" ne porte alors que sur des float, ce que mypy propage jusqu'à la
    # soustraction plus bas — contrairement à un filtre sur les objets Copie
    # eux-mêmes, où le narrowing ne survivrait pas à la sortie de la liste.
    notees = [
        (c.date_soumission, c.notes_finales)
        for c in copies if c.notes_finales is not None
    ]
    if len(notees) < 2:
        return "insuffisant"

    notees_triees = sorted(notees, key=lambda paire: paire[0])
    (_, note_avant_derniere), (_, note_derniere) = notees_triees[-2], notees_triees[-1]
    ecart = note_derniere - note_avant_derniere

    if ecart >= SEUIL_TENDANCE:
        return "progresse"
    if ecart <= -SEUIL_TENDANCE:
        return "regresse"
    return "stagne"
