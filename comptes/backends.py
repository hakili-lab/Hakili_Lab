"""
Authentification adossée au Google Sheet personnel.

Ce que ça change par rapport à Streamlit
----------------------------------------
Avant : un booléen dans `st.session_state`, sans jeton, sans expiration, sans
protection CSRF, sans vérification d'autorisation par requête. Après : une vraie
session Django signée, expirante, avec CSRF et décorateurs de permission.

Ce que ça ne change pas — et c'est voulu
----------------------------------------
Le **Sheet continue de faire foi** (D-CEO-21) : le PIN n'est jamais copié en base,
il est relu dans le Sheet à chaque connexion. Un nom retiré du Sheet ne peut plus
se connecter, même si son `User` Django existe encore. Le compte Django est un
miroir servant à porter la session, pas une identité concurrente — il est créé
avec un mot de passe inutilisable, donc inexploitable par un autre chemin.

Limite assumée, identique à l'existant : le rôle et les affectations sont lus au
moment de la connexion et gardés en session pour la durée de celle-ci (8 h). Une
modification du Sheet en cours de session n'est donc pas vue immédiatement. Les
relire à chaque requête coûterait un appel réseau par page ; le comportement
actuel de Streamlit est le même.
"""
from __future__ import annotations

import logging

from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User

# Import du MODULE, pas des fonctions : une fonction importée par son nom fige
# la référence à l'import et devient impossible à simuler en test sans connaître
# tous les modules qui l'ont importée.
from src.integrations import google_sheets
from src.services.auth_service import authentifier
from src.services.identite_service import roles_valides_de

logger = logging.getLogger(__name__)


class EchecConnexion(Exception):
    """Motif d'échec destiné à être montré à l'utilisateur."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def cle_personne(personne: dict) -> str:
    """Identifiant stable d'une personne — la même clé que celle qui regroupe ses
    affectations dans le Sheet, pour qu'un compte Django corresponde exactement à
    une personne du Sheet."""
    return google_sheets._cle_nom(personne.get("nom", ""), personne.get("prenom", ""))


def trouver_personne(cle: str) -> dict | None:
    """Relit le Sheet et retrouve la personne par sa clé. `None` si elle n'y est
    plus — c'est ce qui fait qu'un retrait du Sheet retire l'accès."""
    for personne in google_sheets.get_personnel():
        if cle_personne(personne) == cle:
            return personne
    return None


#: Sentinelle : distingue « paramètre absent » de « paramètre vide ».
_NON_FOURNI = object()


class SheetBackend(BaseBackend):
    """Authentifie sur (clé de personne, PIN) en relisant le Sheet.

    Lève `EchecConnexion` avec un motif précis au lieu de retourner `None` sans
    explication : « aucun PIN configuré » et « PIN incorrect » demandent des
    messages différents, et « rôle non reconnu » doit renvoyer vers le docteur.
    `comptes.views.connexion` appelle ce backend **directement** et compte
    dessus.

    Mais Django, lui, essaie les backends **en chaîne** : `/admin/login/` appelle
    `authenticate(request, username=…, password=…)` et attend qu'un backend qui
    ne reconnaît pas ces identifiants retourne `None`, pour laisser sa chance au
    suivant — ici `ModelBackend`. Lever à ce moment-là interrompt la chaîne et
    rend l'administration Django inaccessible par une erreur 500.

    D'où la sentinelle : `cle` **absent** signifie « ce ne sont pas mes
    identifiants » et retourne `None` ; `cle` **vide** signifie « le formulaire de
    connexion a été envoyé sans nom » et mérite son message.
    """

    def authenticate(self, request, cle=_NON_FOURNI, pin=None, **kwargs):  # noqa: D102
        if cle is _NON_FOURNI:
            return None
        if not cle:
            raise EchecConnexion(
                "nom_absent", "Veuillez sélectionner votre nom dans la liste."
            )

        personne = trouver_personne(cle)
        if personne is None:
            logger.warning("[AUTH] Tentative de connexion pour une personne absente du Sheet.")
            raise EchecConnexion(
                "personne_absente",
                "Ce nom n'est plus dans le Sheet du personnel — contactez le docteur.",
            )

        resultat = authentifier(personne, pin or "")
        if resultat.status == "pin_absent":
            raise EchecConnexion(
                "pin_absent",
                "Aucun code PIN n'a été configuré pour ce compte — contactez le docteur.",
            )
        if resultat.status == "pin_incorrect":
            raise EchecConnexion("pin_incorrect", "Code incorrect.")

        roles = roles_valides_de(personne)
        if not roles:
            raise EchecConnexion(
                "role_inconnu",
                f"Rôle non reconnu dans le Sheet ({personne.get('role', '')!r}) — "
                "contactez le docteur.",
            )

        utilisateur = self._miroir(personne, roles)
        # La personne du Sheet est attachée au passage : la vue en a besoin pour
        # ouvrir la session, et une seconde recherche relirait le Sheet pour rien.
        # Attribut transitoire, jamais persisté.
        utilisateur.personne_sheet = personne
        return utilisateur

    def get_user(self, user_id):  # noqa: D102
        return User.objects.filter(pk=user_id).first()

    @staticmethod
    def _miroir(personne: dict, roles: list[str]) -> User:
        """Crée ou met à jour le compte Django miroir.

        Mot de passe inutilisable : le PIN reste dans le Sheet et ne doit pas
        avoir d'équivalent en base, sinon on recréerait la seconde source de
        vérité que le projet a déjà démolie deux fois (D-CEO-20, D-CEO-21).

        `is_staff` est accordé aux administrateurs pour qu'ils atteignent l'admin
        Django, où se consulte le référentiel.
        """
        from src.db.models import UserRole

        est_admin = UserRole.admin.value in roles
        utilisateur, cree = User.objects.get_or_create(
            username=cle_personne(personne),
            defaults={
                "first_name": personne.get("prenom", "")[:150],
                "last_name": personne.get("nom", "")[:150],
                "email": personne.get("email", "") or "",
            },
        )
        if cree:
            utilisateur.set_unusable_password()

        # Le Sheet fait foi : on réaligne à chaque connexion.
        utilisateur.first_name = personne.get("prenom", "")[:150]
        utilisateur.last_name = personne.get("nom", "")[:150]
        utilisateur.email = personne.get("email", "") or ""
        utilisateur.is_staff = est_admin
        utilisateur.is_superuser = est_admin
        utilisateur.is_active = True
        utilisateur.save()
        return utilisateur
