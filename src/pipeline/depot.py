"""Où le pipeline dépose ce qu'il produit — sans savoir dans quoi.

Le pipeline crée une copie, y attache un scan, un rapport, une remédiation, et
met à jour une note et une classe. Ces cinq gestes touchent la base ; or
`src/pipeline/` ne doit dépendre d'aucun framework, et la base appartient
désormais à Django (D-CEO-40). Ce module est la couture entre les deux : un
contrat de cinq méthodes, et un dépôt courant que l'application installe au
démarrage.

**Pourquoi pas un import direct de Django ici.** Django est aujourd'hui le seul
appelant du pipeline — l'argument « deux interfaces à servir » est mort avec
Streamlit (D-CEO-39). Mais cette discipline vient de prouver sa valeur : le
retrait de Streamlit, 3 106 lignes, n'a touché aucun test, précisément parce que
`src/` ne connaissait pas l'interface. Un import de Django ici obligerait aussi
les 239 tests de `tests/` à configurer Django pour importer le pipeline.

**Pourquoi un dépôt neutre par défaut, et pas une erreur.** Sans base
configurée, le pipeline doit corriger quand même — c'est un mode de
fonctionnement réel (portail de consultation, essais hors ligne, tests du
pipeline). L'écriture en base est best-effort à tous ses points d'injection sauf
un (D-CEO-19) ; un dépôt qui ne fait rien est donc le comportement juste, pas un
pis-aller. La seule vérification non best-effort — l'élève existe-t-il dans le
Sheet — ne passe pas par ici : elle est dans le pipeline, avant tout appel IA.
"""
from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class DepotCopies(Protocol):
    """Ce que le pipeline attend de sa persistance. Cinq gestes, pas un de plus."""

    def creer_copie(
        self, *, copy_id: str, identifiant_hakili: str, classe: str, annee_scolaire: str
    ) -> None:
        """Crée la copie si elle n'existe pas — l'appel est rejouable."""

    def ajouter_document(self, *, copy_id: str, type_document: str, contenu: bytes) -> None:
        """Attache un fichier à la copie, en remplaçant celui du même type."""

    def maj_notes(self, *, copy_id: str, notes_finales: float | None) -> None: ...

    def maj_classe(self, *, copy_id: str, classe: str) -> None: ...


class _DepotNeutre:
    """Aucune base configurée : le pipeline tourne, rien n'est écrit."""

    def creer_copie(self, **_) -> None: ...
    def ajouter_document(self, **_) -> None: ...
    def maj_notes(self, **_) -> None: ...
    def maj_classe(self, **_) -> None: ...


_depot: DepotCopies = _DepotNeutre()


def installer_depot(depot: DepotCopies) -> None:
    """Installe le dépôt courant. Appelé une fois au démarrage de l'application."""
    global _depot
    _depot = depot
    logger.info("Dépôt de copies installé : %s", type(depot).__name__)


def depot() -> DepotCopies:
    return _depot
