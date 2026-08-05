"""
Rendu des expressions mathématiques à l'écran.

Extrait de l'ancienne interface Streamlit lors de la migration vers Django
(retirée depuis, D-CEO-39). Sans ces fonctions,
une réponse d'élève s'afficherait « x^2 » et « <= » au lieu de x² et ≤ : ce n'est
pas cosmétique, c'est ce que l'enseignant compare pour décider d'une note dans le
tableau de validation.

Aucune dépendance à un framework : les conversions viennent de
`src/pipeline/math_format.py`, déjà utilisé par la génération des PDF.
"""
from __future__ import annotations

import re

from src.pipeline.math_format import (
    ascii_math_upgrade,
    humanize_ids_in_text,
    math_to_html,
)

# Certains signes combinants sont mal rendus par les polices d'interface : la
# flèche de vecteur au-dessus d'un couple de lettres se décale ou s'affiche en
# carré. On la remplace par une flèche autonome, lisible et sans ambiguïté.
_SUBSTITUTIONS: list[tuple[str, str]] = [
    ("⃗", "→"),   # vecteur : AB⃗ → AB→
    ("⃖", "←"),
    ("⃡", "↔"),
    ("⃑", "⇁"),
]

# Exposants Unicode, pour les contextes où aucune balise HTML n'est possible
# (attribut `title`, texte d'option, nom de fichier).
_EXPOSANTS = str.maketrans("0123456789n+-", "⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ⁺⁻")


def nettoyer(texte: str) -> str:
    """Remplace les signes combinants mal rendus."""
    for signe, remplacement in _SUBSTITUTIONS:
        texte = texte.replace(signe, remplacement)
    return texte


def math_html(texte) -> str:
    """Notation mathématique en HTML : `x^2` → `x<sup>2</sup>`, `7/12` en fraction,
    `<=` → `≤`. L'échappement HTML est fait par `math_to_html`.

    Contrairement au PDF, aucune police de repli n'est nécessaire : le navigateur
    rend nativement ∈, ⊂, ², √ — les symboles Unicode sont conservés tels quels.
    """
    return math_to_html(nettoyer(humanize_ids_in_text(str(texte))))


def math_texte(texte) -> str:
    """Notation mathématique en texte pur, sans balise : `^2` → `²`,
    `^(3-5)` → `³⁻⁵`, `<=` → `≤`.

    Pour les endroits où du HTML s'afficherait littéralement.
    """
    resultat = nettoyer(humanize_ids_in_text(ascii_math_upgrade(str(texte))))
    return re.sub(
        r"\^\(?([0-9n+-]{1,3})\)?",
        lambda m: m.group(1).translate(_EXPOSANTS),
        resultat,
    )
