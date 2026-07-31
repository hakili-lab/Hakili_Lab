"""Connexion, déconnexion et changement de casquette."""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render

from src.integrations import google_sheets
from src.integrations.google_sheets import GoogleSheetsError
from src.services.identite_service import (
    LIBELLES_CASQUETTE,
    roles_valides_de,
)

from comptes.backends import EchecConnexion, SheetBackend, cle_personne
from comptes.session import (
    acces_libre,
    casquette_courante,
    changer_casquette,
    connexion_requise,
    ouvrir_session,
    personne_courante,
)

logger = logging.getLogger(__name__)


def _personnel_ou_message(request) -> list[dict]:
    """Le Sheet peut être injoignable. On distingue la coupure réseau — où il faut
    inviter à réessayer — d'un problème de configuration, où réessayer ne sert à
    rien. Même intention que `_lire_sheets_avec_secours` côté Streamlit."""
    try:
        return google_sheets.get_personnel()
    except GoogleSheetsError as exc:
        logger.warning("[SHEETS] Lecture du personnel impossible : %s", exc)
        messages.error(
            request,
            "La liste du personnel est momentanément indisponible. "
            "Réessayez dans un instant ; si le problème persiste, contactez le docteur.",
        )
        return []


def connexion(request):
    if request.user.is_authenticated and personne_courante(request):
        return redirect("suivi_web:accueil")

    personnel = _personnel_ou_message(request)
    personnel = sorted(
        personnel, key=lambda p: (p.get("nom", "").upper(), p.get("prenom", ""))
    )
    cle_choisie = ""

    if request.method == "POST":
        cle_choisie = request.POST.get("cle", "")
        try:
            utilisateur = SheetBackend().authenticate(
                request, cle=cle_choisie, pin=request.POST.get("pin", "")
            )
        except EchecConnexion as echec:
            # Pas de journalisation du PIN ni du nom : un log ne doit pas devenir
            # une source de données personnelles.
            logger.info("[AUTH] Connexion refusée (%s).", echec.code)
            messages.error(request, echec.message)
        else:
            personne = utilisateur.personne_sheet
            login(request, utilisateur, backend="comptes.backends.SheetBackend")
            ouvrir_session(request, personne)
            messages.success(
                request, f"Bienvenue {personne['prenom']} {personne['nom']}"
            )
            return redirect("suivi_web:accueil")

    return render(
        request,
        "comptes/connexion.html",
        {
            "personnel": [
                {"cle": cle_personne(p), "libelle": f"{p.get('nom', '')} {p.get('prenom', '')}".strip()}
                for p in personnel
            ],
            "cle_choisie": cle_choisie,
        },
    )


def deconnexion(request):
    logout(request)
    messages.info(request, "Vous êtes déconnecté.")
    return redirect("comptes:connexion")


@connexion_requise
def choisir_casquette(request):
    """Change le rôle sous lequel la personne travaille, sans la déconnecter.

    En POST seulement : un changement de périmètre n'est pas une navigation, il ne
    doit pas pouvoir arriver par un simple lien cliqué ailleurs.
    """
    if request.method != "POST":
        return redirect("suivi_web:accueil")

    demandee = request.POST.get("casquette", "")
    if changer_casquette(request, demandee):
        messages.success(
            request,
            f"Vous travaillez maintenant comme {LIBELLES_CASQUETTE.get(demandee, demandee)}.",
        )
    else:
        messages.error(request, "Ce rôle ne vous est pas attribué.")
    return redirect(request.POST.get("suivant") or "suivi_web:accueil")


def contexte_utilisateur(request) -> dict:
    """Processeur de contexte : rend la personne, sa casquette et ses rôles
    disponibles dans tous les gabarits, pour l'en-tête et le sélecteur."""
    personne = personne_courante(request)
    if not personne:
        return {"acces_libre": acces_libre()}
    roles = roles_valides_de(personne)
    return {
        "acces_libre": acces_libre(),
        "personne": personne,
        "casquette": casquette_courante(request),
        "casquettes_possibles": [
            {"valeur": r, "libelle": LIBELLES_CASQUETTE.get(r, r)} for r in roles
        ],
    }
