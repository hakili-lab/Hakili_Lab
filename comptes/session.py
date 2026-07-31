"""
Ce que la session porte, et comment les vues y accèdent.

La session garde la personne du Sheet et la **casquette active** (rôle sous lequel
elle travaille, pour les doubles rôles). Les vues n'appellent jamais le Sheet
directement : elles demandent `utilisateur_courant(request)`, qui rend le dict
attendu par `get_accessible_eleves` et `can_access_eleve` — les mêmes fonctions de
permission qu'avant, non dupliquées.
"""
from __future__ import annotations

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from src.db.models import UserRole
from src.services.identite_service import (
    casquette_par_defaut,
    roles_valides_de,
    vue_utilisateur_pour_casquette,
)

CLE_PERSONNE = "hakili_personne"
CLE_CASQUETTE = "hakili_casquette"

#: Identité de substitution quand l'accès libre est actif (développement seul).
#: Rôle administrateur pour que tous les élèves soient visibles — sans Sheets il
#: n'y en a de toute façon aucun, mais les vues attendent un utilisateur valide.
_PERSONNE_ACCES_LIBRE = {
    "nom": "ACCÈS LIBRE",
    "prenom": "Développement",
    "role": UserRole.admin.value,
    "roles": [UserRole.admin.value],
    "pin": "",
    "email": "",
    "affectations": [],
    "centres_responsable": [],
}


def acces_libre() -> bool:
    """Vrai si l'application tourne sans contrôle d'accès.

    Le réglage est verrouillé sur DEBUG dans les settings : il ne peut pas être
    actif en production, même si la variable d'environnement y traîne.
    """
    from django.conf import settings

    return bool(getattr(settings, "ACCES_LIBRE", False))


def ouvrir_session(request, personne: dict) -> None:
    """Enregistre la personne et choisit sa casquette de départ."""
    roles = roles_valides_de(personne)
    request.session[CLE_PERSONNE] = _serialisable(personne)
    request.session[CLE_CASQUETTE] = casquette_par_defaut(roles)


def personne_courante(request) -> dict | None:
    if acces_libre():
        return dict(_PERSONNE_ACCES_LIBRE)
    return request.session.get(CLE_PERSONNE)


def casquette_courante(request) -> str:
    personne = personne_courante(request)
    if not personne:
        return ""
    roles = roles_valides_de(personne)
    casquette = request.session.get(CLE_CASQUETTE, "")
    # Une casquette qui n'est plus dans les rôles (Sheet modifié, session
    # ancienne) est remplacée plutôt que de laisser passer un périmètre erroné.
    if casquette not in roles:
        casquette = casquette_par_defaut(roles)
        request.session[CLE_CASQUETTE] = casquette
    return casquette


def changer_casquette(request, casquette: str) -> bool:
    """Refuse une casquette que la personne ne porte pas — sinon un utilisateur
    pourrait s'attribuer un périmètre plus large en forgeant une requête."""
    personne = personne_courante(request)
    if not personne or casquette not in roles_valides_de(personne):
        return False
    request.session[CLE_CASQUETTE] = casquette
    return True


def utilisateur_courant(request) -> dict | None:
    """Dict utilisateur attendu par les fonctions de permission existantes."""
    personne = personne_courante(request)
    if not personne:
        return None
    return vue_utilisateur_pour_casquette(personne, casquette_courante(request))


def est_admin(request) -> bool:
    utilisateur = utilisateur_courant(request)
    return bool(utilisateur and utilisateur["role_enum"] == UserRole.admin)


def connexion_requise(vue):
    """`login_required` plus la garantie que la session porte bien une personne
    du Sheet — une session Django valide dont le contenu Sheet a disparu (purge,
    changement de format) ne doit pas laisser passer une vue sans périmètre.

    Court-circuité par l'accès libre, réservé au développement (voir settings)."""

    @wraps(vue)
    def _enveloppe(request, *args, **kwargs):
        if acces_libre():
            return vue(request, *args, **kwargs)
        return _protege(request, *args, **kwargs)

    @wraps(vue)
    @login_required
    def _protege(request, *args, **kwargs):
        if not personne_courante(request):
            from django.contrib.auth import logout
            from django.shortcuts import redirect

            logout(request)
            return redirect("comptes:connexion")
        return vue(request, *args, **kwargs)

    return _enveloppe


def admin_requis(vue):
    @wraps(vue)
    @connexion_requise
    def _enveloppe(request, *args, **kwargs):
        if not acces_libre() and not est_admin(request):
            raise PermissionDenied("Réservé aux administrateurs.")
        return vue(request, *args, **kwargs)

    return _enveloppe


def _serialisable(personne: dict) -> dict:
    """La session est sérialisée en JSON : les tuples d'affectation en
    deviendraient des listes au prochain chargement, et `vue_utilisateur_pour_
    casquette` compare des tuples. On normalise ici, une fois, plutôt que de
    laisser une différence de type surgir plus tard côté permissions.
    """
    copie = {
        cle: valeur for cle, valeur in personne.items() if not cle.startswith("_")
    }
    copie["affectations"] = [
        [centre, classe] for centre, classe in personne.get("affectations", [])
    ]
    copie["centres_responsable"] = list(personne.get("centres_responsable", []))
    copie["roles"] = list(personne.get("roles", []))
    return copie
