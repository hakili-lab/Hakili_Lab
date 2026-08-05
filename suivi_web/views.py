"""
Vues de suivi — migration des écrans Streamlit.

Les règles de permission ne sont pas réécrites : `get_accessible_eleves` et
`can_access_eleve` (`src/services/user_service.py`) sont appelées telles quelles.
Une divergence entre ces deux fonctions a déjà causé un bug par le passé (un
enseignant se voyait refuser l'accès au profil d'un élève sans copie) — les
dupliquer ici recréerait le risque.
"""
from __future__ import annotations

import logging

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from src.core.tendance import calculer_tendance
from src.integrations.google_sheets import GoogleSheetsError
from src.services.identite_service import filtrer_par_recherche
from src.services.user_service import get_accessible_eleves

from comptes.session import admin_requis, connexion_requise, utilisateur_courant
from suivi.models import Copie, EtatSession
from suivi_web.jetons import identifiant_depuis_jeton, jeton_eleve

logger = logging.getLogger(__name__)


_STYLE_TENDANCE = {
    "progresse": ("progresse", "Progresse"),
    "stagne": ("stagne", "Stagne"),
    "regresse": ("regresse", "En baisse"),
    "insuffisant": ("insuffisant", "Pas assez de données"),
}


def _eleves_accessibles(request, utilisateur: dict) -> list[dict] | None:
    """`None` signale une lecture impossible — distinct d'une liste vide, qui veut
    dire « aucun élève dans votre périmètre ». Confondre les deux ferait croire à
    un responsable que son centre est vide alors que le réseau est coupé."""
    try:
        return get_accessible_eleves(utilisateur)
    except GoogleSheetsError as exc:
        logger.warning("[SHEETS] Lecture des élèves impossible : %s", exc)
        messages.error(
            request,
            "La liste des élèves est momentanément indisponible. Réessayez dans un instant.",
        )
        return None


def _copies_par_eleve(request, eleves: list[dict]) -> dict[str, list]:
    """Copies de tous les élèves du périmètre, en une seule requête.

    Une requête par élève ferait N appels pour un centre à N élèves.

    Si la base est injoignable — Neon se met en veille, le réseau coupe — la vue
    ne doit pas rendre une erreur : la liste des élèves vient des Sheets et reste
    parfaitement affichable. On dégrade en retirant la tendance, en le disant, au
    lieu de refuser toute la page pour une colonne manquante.
    """
    identifiants = [e.get("identifiant_hakili", "") for e in eleves]
    if not identifiants:
        return {}
    try:
        # Une seule requête pour toute la liste : un centre peut compter
        # plusieurs dizaines d'élèves, et une requête par élève (N+1) rendrait
        # l'accueil inutilisable.
        par_identifiant: dict[str, list[Copie]] = {i: [] for i in identifiants}
        for copie in Copie.objects.filter(identifiant_hakili__in=identifiants):
            par_identifiant.setdefault(copie.identifiant_hakili, []).append(copie)
        return par_identifiant
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DB] Copies indisponibles, tendance non calculée : %s", exc)
        messages.warning(
            request,
            "Les notes ne sont pas accessibles pour l'instant : la tendance n'est "
            "pas affichée. La liste des élèves, elle, est à jour.",
        )
        return {}


@connexion_requise
def accueil(request):
    """Liste des élèves du périmètre, avec leur tendance.

    La tendance vient de `calculer_tendance` (`src/core/tendance.py`, seuil 1,0) —
    réutilisée telle quelle, pas réimplémentée.
    """
    utilisateur = utilisateur_courant(request)
    eleves = _eleves_accessibles(request, utilisateur)

    recherche = request.GET.get("q", "")
    lignes: list[dict] = []
    en_baisse = 0

    if eleves:
        eleves = filtrer_par_recherche(
            eleves, recherche, lambda e: f"{e.get('prenom', '')} {e.get('nom', '')}"
        )
        copies_par_eleve = _copies_par_eleve(request, eleves)

        for eleve in eleves:
            copies = copies_par_eleve.get(eleve.get("identifiant_hakili", ""), [])
            tendance = calculer_tendance(copies)
            classe_css, libelle = _STYLE_TENDANCE.get(tendance, ("insuffisant", tendance))
            notes = [c.notes_finales for c in copies if c.notes_finales is not None]
            lignes.append(
                {
                    "eleve": eleve,
                    "jeton": jeton_eleve(eleve.get("identifiant_hakili", "")),
                    "tendance": classe_css,
                    "tendance_libelle": libelle,
                    "nb_copies": len(copies),
                    "derniere_note": notes[-1] if notes else None,
                }
            )
            if tendance == "regresse":
                en_baisse += 1

        # Les élèves en baisse d'abord : c'est ce qu'un responsable doit voir en
        # premier, pas l'ordre alphabétique.
        ordre = {"regresse": 0, "stagne": 1, "progresse": 2, "insuffisant": 3}
        lignes.sort(key=lambda ligne: ordre.get(ligne["tendance"], 9))

    return render(
        request,
        "suivi_web/accueil.html",
        {
            "rubrique": "accueil",
            "lignes": lignes,
            "en_baisse": en_baisse,
            "recherche": recherche,
            "lecture_impossible": eleves is None,
        },
    )


_DOC_ORDRE = ["scan", "rapport", "remediation"]
_DOC_LIBELLES = {"scan": "Scan", "rapport": "Rapport", "remediation": "Remédiation"}


def _type_reel(donnees: bytes) -> tuple[str, str]:
    """Type réel d'un document stocké en base, d'après ses premiers octets.

    Le scan peut être un PDF ou une photo selon ce qui a été déposé, contrairement
    au rapport et à la remédiation toujours générés en PDF. On ne se fie donc pas
    au champ `type`, qui dit le rôle du document, pas son format.
    """
    if donnees[:4] == b"%PDF":
        return "application/pdf", "pdf"
    if donnees[:3] == b"\xff\xd8\xff":
        return "image/jpeg", "jpg"
    if donnees[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", "png"
    return "application/octet-stream", "bin"


def _eleve_autorise(request, identifiant: str):
    """Retrouve l'élève et vérifie le droit d'accès, ou lève 404 / 403.

    404 quand l'élève n'existe pas, 403 quand il existe mais hors périmètre : ne
    pas confondre les deux, sinon un enseignant apprendrait par la différence de
    message quels élèves existent dans les autres centres.
    """
    from src.integrations.google_sheets import get_eleve_by_identifiant
    from src.services.user_service import can_access_eleve

    utilisateur = utilisateur_courant(request)
    try:
        eleve = get_eleve_by_identifiant(identifiant)
    except GoogleSheetsError as exc:
        logger.warning("[SHEETS] Élève introuvable (lecture impossible) : %s", exc)
        raise Http404("Élève momentanément inaccessible") from exc

    if eleve is None:
        raise Http404("Élève inconnu")

    # `can_access_eleve` prend une session en premier argument mais ne l'utilise
    # pas : le critère est celui du Sheet, pas de la base. On passe None plutôt
    # que d'ouvrir une connexion inutile.
    if not can_access_eleve(None, utilisateur, eleve):
        raise PermissionDenied("Cet élève n'est pas dans votre périmètre.")
    return eleve


@connexion_requise
def eleve_detail(request, jeton: str):
    """Profil d'un élève : tendance, résumé chiffré, copies dans l'ordre
    chronologique avec leurs documents.

    Une seule vue pour les trois rôles, cloisonnée par `can_access_eleve`. La
    version Streamlit avait des onglets Historique / Comparaison séparés en plus
    du profil ; sur un même élève ils affichaient la même chronologie — les
    fusionner supprime la duplication sans rien retirer.
    """
    identifiant = identifiant_depuis_jeton(jeton)
    if identifiant is None:
        # Jeton forgé ou signé avec une autre clé : rien à révéler de plus.
        raise Http404("Lien invalide")
    eleve = _eleve_autorise(request, identifiant)

    copies, entrees, lecture_ok = [], [], True
    try:
        copies = list(
            Copie.objects.filter(identifiant_hakili=identifiant)
            .order_by("-date_soumission")
            .prefetch_related("documents")
        )
        for copie in copies:
            documents = sorted(
                copie.documents.all(),
                key=lambda d: _DOC_ORDRE.index(d.type) if d.type in _DOC_ORDRE else 9,
            )
            entrees.append(
                {
                    "copie": copie,
                    "jeton": jeton_eleve(copie.copy_id),
                    "documents": [
                        {"type": doc.type, "libelle": _DOC_LIBELLES.get(doc.type, doc.type)}
                        for doc in documents
                    ],
                }
            )
    except Exception as exc:  # noqa: BLE001
        lecture_ok = False
        logger.warning("[DB] Historique indisponible pour un élève : %s", exc)
        messages.warning(
            request,
            "Les copies de cet élève ne sont pas accessibles pour l'instant.",
        )

    tendance = calculer_tendance(copies)
    classe_css, libelle = _STYLE_TENDANCE.get(tendance, ("insuffisant", tendance))
    notes = [c.notes_finales for c in copies if c.notes_finales is not None]

    from suivi.models import Session

    parcours = [
        {"session": s, "jeton": jeton_eleve(str(s.pk))}
        for s in Session.objects.filter(identifiant_hakili=identifiant)
    ]

    return render(
        request,
        "suivi_web/eleve_detail.html",
        {
            "rubrique": "accueil",
            "eleve": eleve,
            "entrees": entrees,
            "tendance": classe_css,
            "tendance_libelle": libelle,
            "nb_copies": len(copies),
            "derniere_note": notes[-1] if notes else None,
            "lecture_ok": lecture_ok,
            "parcours": parcours,
        },
    )


@connexion_requise
def document(request, jeton: str, doc_type: str):
    """Sert un document (scan, rapport, remédiation).

    Le droit d'accès est revérifié ici et pas seulement sur la page qui affiche le
    lien : sans cela, une URL devinée suffirait à récupérer la copie d'un élève
    d'un autre centre.
    """
    from src.services.identite_service import nom_fichier_document

    copy_id = identifiant_depuis_jeton(jeton)
    if copy_id is None:
        raise Http404("Lien invalide")

    copie = Copie.objects.filter(copy_id=copy_id).first()
    if copie is None:
        raise Http404("Copie inconnue")

    eleve = _eleve_autorise(request, copie.identifiant_hakili)

    doc = copie.documents.filter(type=doc_type).first()
    if doc is None:
        raise Http404("Document inconnu")
    donnees = bytes(doc.fichier)
    date_copie = copie.date_soumission

    mime, extension = _type_reel(donnees)
    nom = nom_fichier_document(
        nom=eleve.get("nom", ""),
        prenom=eleve.get("prenom", ""),
        doc_type=doc_type,
        date=date_copie,
    )

    reponse = HttpResponse(donnees, content_type=mime)
    # `inline` pour l'aperçu, `attachment` quand on veut le fichier : le
    # navigateur affiche PDF et images nativement, il n'y a donc rien à convertir
    # en PNG comme le devait Streamlit.
    disposition = "attachment" if request.GET.get("telecharger") else "inline"
    reponse["Content-Disposition"] = f'{disposition}; filename="{nom}.{extension}"'
    return reponse


@connexion_requise
def session_detail(request, jeton: str):
    """Parcours de remédiation d'un élève : problèmes, plan, inscription."""
    from suivi.models import EtatProbleme, Session
    from suivi.plan import construire

    identifiant = identifiant_depuis_jeton(jeton)
    if identifiant is None:
        raise Http404("Lien invalide")

    session = get_object_or_404(Session, pk=identifiant)
    eleve = _eleve_autorise(request, session.identifiant_hakili)

    plan = construire(session)
    return render(
        request,
        "suivi_web/session_detail.html",
        {
            "rubrique": "accueil",
            "session": session,
            "eleve": eleve,
            "jeton": jeton,
            "jeton_eleve": jeton_eleve(session.identifiant_hakili),
            "plan": plan,
            "hypotheses": session.problemes.filter(
                etat=EtatProbleme.HYPOTHESE
            ).select_related("competence", "type_erreur"),
            "ecartes": session.problemes.filter(
                etat=EtatProbleme.ECARTE
            ).select_related("competence", "type_erreur"),
            "peut_inscrire": session.etat
            in (EtatSession.ATTENTE_INSCRIPTION, EtatSession.HORS_DISPOSITIF),
            "palier_c": session.palier == "C",
        },
    )


@connexion_requise
def inscrire(request, jeton: str):
    """Inscrit l'élève au programme — la décision humaine du cycle.

    En POST seulement : une inscription engage un volume horaire et,
    vraisemblablement, une facturation. Elle ne doit pas pouvoir arriver par un
    lien cliqué depuis une autre page.
    """
    from django.core.exceptions import ValidationError

    from suivi.models import Session

    identifiant = identifiant_depuis_jeton(jeton)
    if identifiant is None:
        raise Http404("Lien invalide")

    session = get_object_or_404(Session, pk=identifiant)
    _eleve_autorise(request, session.identifiant_hakili)

    if request.method != "POST":
        return redirect("suivi_web:session_detail", jeton=jeton)

    forcer = bool(request.POST.get("forcer"))
    motif = request.POST.get("motif", "")

    try:
        session.inscrire(forcer=forcer, motif=motif)
    except ValidationError as exc:
        for message in exc.messages:
            messages.error(request, message)
    else:
        messages.success(
            request,
            f"{session.problemes.count()} problème(s) en remédiation. "
            f"Volume prévu : {session.cout_total_confirme:g} h.",
        )
    return redirect("suivi_web:session_detail", jeton=jeton)


@admin_requis
def personnel(request):
    """Qui a accès à la plateforme — lecture seule.

    L'ajout et le retrait se font **dans le Google Sheet**, pas ici : le Sheet
    fait foi (D-CEO-21, D-CEO-25), et gérer les comptes des deux côtés recréerait
    la seconde source de vérité que ce projet a démolie deux fois. Cet écran sert
    à vérifier l'état, pas à le modifier.

    Personne n'est masqué — surtout pas les cas problématiques. Une personne sans
    code d'accès ou au rôle non reconnu est justement ce que l'administrateur doit
    voir : elle figure dans le Sheet en croyant avoir accès, et ne peut pas se
    connecter.
    """
    from src.services.identite_service import roles_valides_de

    lignes, probleme = [], 0
    try:
        from src.integrations import google_sheets

        personnes = google_sheets.get_personnel()
    except GoogleSheetsError as exc:
        logger.warning("[SHEETS] Personnel indisponible : %s", exc)
        messages.error(
            request, "La liste du personnel est momentanément indisponible."
        )
        personnes = []

    for personne in personnes:
        roles = roles_valides_de(personne)
        a_un_code = bool(str(personne.get("pin") or "").strip())

        if not roles:
            etat, libelle = "regresse", f"Rôle non reconnu : « {personne.get('role', '')} »"
        elif not a_un_code:
            etat, libelle = "stagne", "Aucun code d'accès — ne peut pas se connecter"
        else:
            etat, libelle = "progresse", "Accès actif"

        if etat != "progresse":
            probleme += 1

        centres = sorted(
            {c for c, _ in personne.get("affectations", []) if c}
        ) or ["—"]
        lignes.append(
            {
                "personne": personne,
                "roles": ", ".join(roles) or "—",
                "centres": ", ".join(centres),
                "etat": etat,
                "libelle": libelle,
            }
        )

    # Les comptes en défaut d'abord : c'est ce qu'il faut corriger dans le Sheet.
    ordre = {"regresse": 0, "stagne": 1, "progresse": 2}
    lignes.sort(key=lambda l: (ordre.get(l["etat"], 9), l["personne"].get("nom", "")))

    return render(
        request,
        "suivi_web/personnel.html",
        {"rubrique": "personnel", "lignes": lignes, "probleme": probleme},
    )


@admin_requis
def statistiques(request):
    """Élèves, centres et copies — mêmes chiffres que la vue Streamlit.

    Les centres sont dérivés des Sheets (`deriver_centres`), pas d'une liste
    figée : le docteur ajoute un centre en l'écrivant dans un Sheet, sans
    modification de code (D-CEO-25). Un centre vu une seule fois est signalé
    comme suspect, jamais bloqué ni corrigé.
    """
    nb_copies = None
    try:
        nb_copies = Copie.objects.count()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DB] Comptage des copies impossible : %s", exc)
        messages.error(request, "Le comptage des copies est momentanément indisponible.")

    eleves, centres, suspects = None, [], []
    try:
        from src.integrations.google_sheets import get_centres_derives, get_eleves

        eleves = get_eleves()
        derives = get_centres_derives()
        centres = sorted(infos["canonique"] for infos in derives.values())
        suspects = sorted(
            infos["canonique"] for infos in derives.values() if infos["suspect"]
        )
    except GoogleSheetsError as exc:
        logger.warning("[SHEETS] Statistiques Sheets indisponibles : %s", exc)
        messages.error(request, "Les données élèves sont momentanément indisponibles.")

    if suspects:
        messages.warning(
            request,
            "Centre(s) vu(s) une seule fois, à vérifier dans les Sheets : "
            + ", ".join(suspects),
        )

    return render(
        request,
        "suivi_web/statistiques.html",
        {
            "rubrique": "statistiques",
            "nb_eleves": len(eleves) if eleves is not None else None,
            "nb_centres": len(centres),
            "nb_copies": nb_copies,
            "centres": centres,
        },
    )
