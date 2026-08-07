"""Géométrie de la courbe de progression d'un élève (note /20 par copie).

Même esprit que tendance.py : une fonction pure, testable indépendamment de
Django et du rendu — le template ne fait qu'assembler les valeurs déjà
calculées ici, il n'invente aucune coordonnée.
"""
from __future__ import annotations

from typing import Protocol

_LARGEUR = 600
_HAUTEUR = 180
_PAD_GAUCHE = 32
_PAD_DROITE = 40  # assez pour l'étiquette de fin ("20,00") sans déborder du viewBox
_PAD_HAUT = 20
_PAD_BAS = 30

_HAUTEUR_UTILE = _HAUTEUR - _PAD_HAUT - _PAD_BAS
_LARGEUR_UTILE = _LARGEUR - _PAD_GAUCHE - _PAD_DROITE

_NOTE_MAX = 20.0


class _CopieNotee(Protocol):
    notes_finales: float | None
    date_soumission: object  # comparable (date) — seul l'ordre relatif compte


def _y(note: float) -> float:
    return _PAD_HAUT + (_NOTE_MAX - note) / _NOTE_MAX * _HAUTEUR_UTILE


def construire_courbe(copies: list[_CopieNotee]) -> dict | None:
    """Points, tracé SVG et repères de la courbe — ou None si moins de deux
    copies notées (une seule note ne trace pas de progression, cf.
    calculer_tendance qui applique la même règle).
    """
    notees = sorted(
        (c for c in copies if c.notes_finales is not None),
        key=lambda c: c.date_soumission,
    )
    if len(notees) < 2:
        return None

    pas = _LARGEUR_UTILE / (len(notees) - 1)
    points = [
        {
            "x": round(_PAD_GAUCHE + i * pas, 1),
            "y": round(_y(c.notes_finales), 1),
            "note": c.notes_finales,
            "date": c.date_soumission,
        }
        for i, c in enumerate(notees)
    ]

    trace = "M " + " L ".join(f"{p['x']},{p['y']}" for p in points)

    reperes_y = [
        {"y": round(_y(v), 1), "valeur": v} for v in (0, 10, 20)
    ]

    return {
        "largeur": _LARGEUR,
        "hauteur": _HAUTEUR,
        "points": points,
        "trace": trace,
        "reperes_y": reperes_y,
        "dernier": points[-1],
    }
