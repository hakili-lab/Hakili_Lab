"""Filtres de gabarit pour les expressions mathématiques.

`{{ reponse|math }}` rend `x^2` en x² et `<=` en ≤. Sans lui, l'enseignant
comparerait des chaînes brutes pour décider d'une note.
"""
from django import template
from django.utils.safestring import mark_safe

from src.services.affichage_math import math_html, math_texte

register = template.Library()


@register.filter(name="math")
def math(valeur):
    """HTML. `math_to_html` échappe déjà le texte : `mark_safe` ne réintroduit
    donc pas d'injection — c'est la fonction de conversion qui garantit
    l'échappement, pas ce filtre."""
    return mark_safe(math_html(valeur))  # noqa: S308


@register.filter(name="math_brut")
def math_brut(valeur):
    """Texte pur, pour les attributs et les contextes sans balise."""
    return math_texte(valeur)
