"""Couche de lecture Google Sheets — source de vérité des élèves et du
personnel (enseignants, responsables, administrateur).

Ce module est le SEUL endroit de l'application qui sait que les données
viennent de Google Sheets, ET le SEUL endroit qui connaît les noms réels de
colonnes de chaque Sheet. Le reste du code appelle get_eleves()/
get_personnel() et travaille uniquement avec des noms LOGIQUES (nom, prenom,
centre, classe, role, pin...) — jamais avec les en-têtes réels. Si le
docteur renomme une colonne, ou si la source change un jour, seul ce fichier
change.

Configuration (voir src/core/config.py, jamais codée en dur ici) :
    GOOGLE_SERVICE_ACCOUNT_FILE   chemin vers la clé JSON du compte de service
    GOOGLE_SHEET_ELEVES_ID        identifiant du Sheet élèves
    GOOGLE_SHEET_PERSONNEL_ID     identifiant du Sheet personnel (unique)

Le personnel (enseignants, responsables, administrateur) vit dans UN SEUL
Sheet fusionné, identifié par une colonne "role" dans le Sheet lui-même — le
rôle ne vient plus du fichier d'origine (il n'y a plus qu'un fichier), il
vient de la donnée.

Authentification (voir src.services.auth_service) : connexion par sélection
du nom dans une liste + code PIN à 4 chiffres, tous deux lus dans le Sheet
personnel à chaque connexion — plus d'email requis, plus de mot de passe
stocké en base.

Centres : il n'existe plus de liste figée de centres autorisés. Les centres
réels sont DÉRIVÉS dynamiquement des valeurs vues dans les Sheets (élèves +
personnel) — voir get_centres_derives() et src.core.centre_normalizer.
deriver_centres. Ajouter un centre se fait dans les Sheets, jamais dans le
code.

Chaque Sheet est lu sur son premier onglet (sheet1). Cache TTL en mémoire
(pas st.cache_data, pour garder ce module indépendant du framework UI comme
le reste de src/services/ — testable sans Streamlit) : voir _CACHE_TTL_SECONDS
et clear_cache().

IMPORTANT — confidentialité : contact_parents est renvoyé par get_eleves()/
get_eleve_by_identifiant() car il sert à construire identifiant_hakili (et
les noms de fichiers téléchargés), mais c'est une donnée personnelle. Il ne
doit JAMAIS être affiché à l'écran par les couches appelantes — seul cet
usage interne est légitime. Même règle pour identifiant_hakili côté écran.
"""
from __future__ import annotations

import logging
import re
import socket
import time
import unicodedata
from datetime import datetime
from typing import Any, Callable

import gspread
import requests.exceptions
from google.auth.exceptions import TransportError as _GoogleAuthTransportError
from google.oauth2.service_account import Credentials

from src.core.centre_normalizer import deriver_centres, fold_centre
from src.core.classe_normalizer import normalize_classe, normalize_classe_avec_serie
from src.core.config import settings
from src.integrations import sheets_factices

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ── Tables de correspondance colonnes ─────────────────────────────────────────
# nom LOGIQUE (utilisé partout ailleurs dans le code) -> nom attendu du Sheet.
# SEUL endroit à modifier si le docteur renomme une colonne — la résolution
# ci-dessous (_resoudre_colonnes) tolère casse/accents/espaces/ponctuation,
# mais compare le nom attendu ci-dessous à l'EXACT après ce repli : jamais
# de correspondance partielle. C'est volontaire — "Contact Parents" ne doit
# JAMAIS matcher "Contact Parents (Whatsapp)", qui est une colonne
# différente (voir tests/test_google_sheets.py).

_COLONNES_ELEVES: dict[str, str] = {
    "nom": "Nom",
    "prenom": "Prenom",
    "classe": "Classe",
    "centre": "Centre",
    "ecole": "Ecole",
    "reprend_la_classe": "Reprend la classe?",
    "boursier": "Boursier",
    "contact_parents": "Contact Parents",
}

# Le personnel (enseignants, responsables, administrateur) est désormais
# distingué par la colonne "role" (valeurs attendues : enseignant /
# responsable / administrateur), lue directement dans le Sheet — plus
# d'inférence à partir du fichier d'origine. Le PIN (4 chiffres, en clair —
# choix du docteur, Sheet réservé, pas d'anti-forçage demandé) sert à la
# connexion. "classe" et "email" sont OPTIONNELLES (voir
# _COLONNES_PERSONNEL_OPTIONNELLES) : un responsable/administrateur n'a pas
# de classe, et un Sheet personnel peut ne pas (ou plus) avoir de colonne
# email — elle reste alors purement informative, ne conditionne plus rien.
# "Matiere" existe dans le Sheet enseignants réel mais n'est pas utilisée
# pour l'instant (pas de filtrage par matière) — signalé ici plutôt que
# silencieusement absente du mapping.
_COLONNES_PERSONNEL: dict[str, str] = {
    "nom": "Nom",
    "prenom": "Prenom",
    "role": "Role",
    "centre": "Centre",
    "classe": "classe",
    "pin": "PIN",
    "email": "Email",
}
_COLONNES_PERSONNEL_OPTIONNELLES: frozenset[str] = frozenset({"classe", "email"})

# Valeurs de rôle attendues dans la colonne "role" — DOIVENT correspondre
# exactement aux valeurs de src.db.models.UserRole (responsable_centre.value,
# enseignant.value). Dupliquées ici en constantes plutôt qu'importées : ce
# module reste volontairement indépendant de src.db (testable sans base de
# données, voir docstring de module).
_ROLE_RESPONSABLE = "responsable"
_ROLE_ENSEIGNANT = "enseignant"

# Entre 60 et 120s demandé : les lectures répétées (rerun Streamlit à chaque
# clic) ne rappellent pas l'API, tout en restant quasi temps réel si le
# docteur modifie un Sheet.
_CACHE_TTL_SECONDS = 90

_cache: dict[str, tuple[float, Any]] = {}

# Cache de REPLI (pas de TTL) : dernière lecture RÉUSSIE de get_eleves()/
# get_personnel(), servie en cas de coupure réseau (voir
# GoogleSheetsConnectiviteError et _cached_avec_repli) — jamais vidé par
# clear_cache(), qui ne touche que le cache court. `_dernier_mode` indique
# si la dernière lecture demandée a servi des données fraîches ou de repli,
# pour le bandeau "hors ligne" côté UI (voir get_statut_lecture).
_cache_repli: dict[str, tuple[datetime, Any]] = {}
_dernier_mode: dict[str, str] = {}


class GoogleSheetsError(RuntimeError):
    """Erreur de lecture Google Sheets — classe de base. Toujours un
    message lisible, jamais une exception brute de gspread/google-auth
    remontée telle quelle à l'écran. Deux sous-classes distinguent la
    CAUSE (voir ci-dessous) : ne jamais lever cette classe directement,
    toujours l'une de ses deux sous-classes."""


class GoogleSheetsConnectiviteError(GoogleSheetsError):
    """Google Sheets injoignable pour une raison RÉSEAU (DNS, timeout,
    connexion refusée) — pas un problème de configuration. L'utilisateur
    peut réessayer, souvent résolu de lui-même (coupure réseau chez
    l'utilisateur). Message DOUX recommandé côté UI ; le cache de repli
    peut servir les dernières données connues à la place de planter."""


class GoogleSheetsConfigError(GoogleSheetsError):
    """Erreur de CONFIGURATION : identifiant de Sheet invalide, partage
    manquant, colonne obligatoire absente. Nécessite une correction du
    docteur — message technique précis à conserver, JAMAIS de repli sur
    d'anciennes données (un vrai problème ne doit jamais être masqué)."""


_MOTS_CLES_CONNECTIVITE = (
    "failed to resolve", "name or service not known", "getaddrinfo failed",
    "connection refused", "network is unreachable", "timed out",
    "max retries exceeded", "temporary failure in name resolution",
    "connection aborted", "remote end closed connection", "nodename nor servname",
)


def _est_erreur_connectivite(exc: Exception) -> bool:
    """Distingue une coupure réseau/DNS/timeout (l'utilisateur peut
    réessayer) d'un problème de configuration (identifiant erroné, partage
    manquant — nécessite une correction). Combine la classe d'exception
    (quand les bibliothèques réseau la fournissent) et une recherche de
    mots-clés dans le message : les exceptions réseau varient selon la
    plateforme et la couche HTTP utilisée par google-auth/gspread, un seul
    critère ne suffit pas à toutes les couvrir de façon fiable."""
    if isinstance(exc, (socket.gaierror, socket.timeout, TimeoutError, ConnectionError)):
        return True
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True
    if isinstance(exc, _GoogleAuthTransportError):
        return True
    message = _exc_message(exc).lower()
    return any(mot in message for mot in _MOTS_CLES_CONNECTIVITE)


def _exc_message(exc: Exception) -> str:
    """Message lisible d'une exception. gspread lève parfois un PermissionError
    nu (sans message propre) où seule exc.__cause__ porte le vrai motif
    ("The caller does not have permission") : on va le chercher là si besoin."""
    text = str(exc)
    if text:
        return text
    if exc.__cause__ is not None and str(exc.__cause__):
        return str(exc.__cause__)
    return type(exc).__name__


def _clean_contact_parents(contact_parents: str) -> str:
    """Ne garde que les chiffres du contact (retire espaces, tirets, points).
    Ex : "76 32 36 44" -> "76323644"."""
    return re.sub(r"\D", "", contact_parents or "")


def build_identifiant_hakili(nom: str, prenom: str, contact_parents: str) -> str:
    """Construit l'identifiant Hakili d'un élève : nom_prenom_contactparents,
    en minuscules, contact nettoyé (chiffres uniquement).

    Fonction pure, sans effet de bord — isolée pour être réutilisée telle
    quelle par le pipeline de correction, sans dupliquer la logique.

    Deux enfants partageant le même contact_parents restent distingués par
    leur prénom (ex : KANAZOE Abdoul / KANAZOE Rachidatou -> deux
    identifiants distincts).
    """
    nom_norm = (nom or "").strip().lower().replace(" ", "_")
    prenom_norm = (prenom or "").strip().lower().replace(" ", "_")
    contact_norm = _clean_contact_parents(contact_parents)
    return f"{nom_norm}_{prenom_norm}_{contact_norm}"


def _cle_nom(nom: str, prenom: str) -> str:
    """Clé de regroupement d'une personne du personnel : nom+prénom repliés
    (casse/accents/espaces ignorés) — remplace l'ancien groupement par
    email, qui n'est plus une clé d'identité fiable depuis que la colonne
    email est optionnelle/informative.

    Limite connue : deux VRAIS homonymes (même nom ET prénom, même graphie)
    dans le personnel seraient fusionnés à tort (leurs affectations
    additionnées comme s'il s'agissait d'une seule personne) — cas jugé
    assez rare pour être accepté ; à signaler au docteur si observé en
    pratique (voir rapport de chantier)."""
    return f"{fold_centre(nom)}|{fold_centre(prenom)}"


def clear_cache() -> None:
    """Vide le cache — à appeler juste après une modification connue d'un
    Sheet pour forcer une relecture immédiate au lieu d'attendre le TTL."""
    _cache.clear()


def _cached(cache_key: str, loader: Callable[[], Any]) -> Any:
    now = time.monotonic()
    cached = _cache.get(cache_key)
    if cached is not None and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]
    data = loader()
    _cache[cache_key] = (now, data)
    return data


def _cached_avec_repli(cache_key: str, loader: Callable[[], Any]) -> Any:
    """Comme _cached, avec un filet de sécurité pour les coupures réseau :
    si la lecture échoue pour une raison de CONNECTIVITÉ
    (GoogleSheetsConnectiviteError) et qu'une lecture précédente a réussi,
    sert ces dernières données connues plutôt que de laisser planter
    l'appelant — voir get_statut_lecture pour signaler ce repli côté UI
    (bandeau "hors ligne").

    Une erreur de CONFIGURATION (GoogleSheetsConfigError) n'utilise JAMAIS
    ce repli et remonte telle quelle : un vrai problème à corriger ne doit
    jamais être masqué par d'anciennes données."""
    try:
        data = _cached(cache_key, loader)
        _cache_repli[cache_key] = (datetime.now(), data)
        _dernier_mode[cache_key] = "frais"
        return data
    except GoogleSheetsConnectiviteError:
        repli = _cache_repli.get(cache_key)
        if repli is not None:
            _dernier_mode[cache_key] = "repli"
            return repli[1]
        raise


def get_statut_lecture(cache_key: str) -> dict:
    """Statut de la dernière lecture de `cache_key` ("eleves" ou
    "personnel") : {"mode": "frais" | "repli", "derniere_synchro": datetime
    | None} — "repli" signifie que les données servies sont la dernière
    lecture réussie (coupure réseau en cours), "derniere_synchro" donne
    l'heure de cette dernière lecture réussie (None si aucune n'a encore eu
    lieu). Utilisé côté UI pour afficher le bandeau "hors ligne"."""
    repli = _cache_repli.get(cache_key)
    return {
        "mode": _dernier_mode.get(cache_key, "frais"),
        "derniere_synchro": repli[0] if repli else None,
    }


def _get_client() -> gspread.Client:
    if not settings.google_service_account_file:
        raise GoogleSheetsConfigError(
            "GOOGLE_SERVICE_ACCOUNT_FILE n'est pas configuré (.env)."
        )
    try:
        creds = Credentials.from_service_account_file(
            settings.google_service_account_file, scopes=_SCOPES
        )
        return gspread.authorize(creds)
    except FileNotFoundError as exc:
        raise GoogleSheetsConfigError(
            f"Fichier de clé Google introuvable : {settings.google_service_account_file}"
        ) from exc
    except Exception as exc:
        if _est_erreur_connectivite(exc):
            raise GoogleSheetsConnectiviteError(_exc_message(exc)) from exc
        raise GoogleSheetsConfigError(f"Authentification Google Sheets échouée : {exc}") from exc


def _fold_header(text: str) -> str:
    """Normalisation TOLÉRANTE d'un en-tête de colonne Sheet : minuscule,
    sans accents, toute ponctuation/espace/tiret bas retiré. Volontairement
    large (casse, accents, espaces, "?", "_") mais EXACTE après ce repli :
    deux en-têtes qui diffèrent par autre chose qu'espace/casse/accent/
    ponctuation restent distincts. C'est ce qui garantit que "Contact
    Parents" et "Contact Parents (Whatsapp)" ne se confondent jamais — la
    seconde replie vers "contactparentswhatsapp", pas "contactparents"."""
    normalized = unicodedata.normalize("NFD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "", ascii_text)


def _resoudre_colonnes(
    en_tetes_reels: list[str],
    mapping_logique: dict[str, str],
    label: str,
    *,
    optionnelles: frozenset[str] = frozenset(),
) -> dict[str, str]:
    """Résout, pour un mapping logique -> nom attendu, quel en-tête RÉEL du
    Sheet correspond à chaque nom logique. Lève GoogleSheetsError listant
    PRÉCISÉMENT la ou les colonnes manquantes ET les en-têtes réellement
    trouvés dans le Sheet, pour que le diagnostic soit immédiat.

    Une colonne logique listée dans `optionnelles` (ex : "classe" pour un
    responsable) n'est pas considérée manquante si son en-tête est absent —
    elle sera simplement vide dans les lignes retournées."""
    index: dict[str, str] = {}
    for h in en_tetes_reels:
        index.setdefault(_fold_header(h), h)

    resolues: dict[str, str] = {}
    manquantes: list[str] = []
    for logique, attendu in mapping_logique.items():
        reel = index.get(_fold_header(attendu))
        if reel is None:
            if logique not in optionnelles:
                manquantes.append(f"'{logique}' (colonne attendue : {attendu!r})")
        else:
            resolues[logique] = reel

    if manquantes:
        raise GoogleSheetsConfigError(
            f"Colonne(s) manquante(s) dans le Sheet {label} : {'; '.join(manquantes)}. "
            f"En-têtes trouvés dans le Sheet : {en_tetes_reels}"
        )
    return resolues


def _fetch_raw_rows(sheet_id: str, label: str) -> list[dict[str, Any]]:
    """Lit les lignes brutes (en-têtes RÉELS en clés) d'un Sheet. Mis en
    cache par IDENTIFIANT DE SHEET (pas par rôle logique) : si deux rôles
    logiques pointent vers le même sheet_id, ceci n'appelle l'API qu'une
    fois — le second appel sert directement depuis le cache."""
    # Développement uniquement : jeu d'identités inventées, à la place de la
    # lecture réseau et d'elle seule. Le branchement est ICI, au ras du réseau,
    # pour que tout l'aval (résolution des colonnes, identifiant_hakili,
    # centres, PIN) s'exécute pour de vrai — voir sheets_factices.actif(), qui
    # refuse de répondre hors DEBUG.
    if sheets_factices.actif():
        factices = sheets_factices.lignes_brutes(sheet_id, label)
        if factices is not None:
            logger.warning(
                "[SHEETS FACTICES] Sheet %s servi depuis le jeu de développement "
                "(%d lignes) — aucune donnée réelle n'est lue.",
                label, len(factices),
            )
            return factices

    if not sheet_id:
        raise GoogleSheetsConfigError(f"L'identifiant du Sheet {label} n'est pas configuré (.env).")

    def _lire() -> list[dict[str, Any]]:
        try:
            client = _get_client()
            worksheet = client.open_by_key(sheet_id).sheet1
            return worksheet.get_all_records()
        except GoogleSheetsError:
            raise
        except Exception as exc:
            if _est_erreur_connectivite(exc):
                raise GoogleSheetsConnectiviteError(_exc_message(exc)) from exc
            if isinstance(exc, (gspread.exceptions.APIError, PermissionError)):
                raise GoogleSheetsConfigError(
                    f"Sheet {label} injoignable ou accès refusé (vérifier que le Sheet est bien "
                    f"partagé en lecture avec le compte de service, et que l'identifiant du Sheet "
                    f"est correct) : {_exc_message(exc)}"
                ) from exc
            raise GoogleSheetsConfigError(f"Lecture du Sheet {label} impossible : {_exc_message(exc)}") from exc

    return _cached(f"raw:{sheet_id}", _lire)


def _fetch_sheet_rows(
    sheet_id: str,
    mapping_logique: dict[str, str],
    label: str,
    *,
    optionnelles: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    """Lit toutes les lignes du premier onglet d'un Sheet et les retourne en
    dicts à clés LOGIQUES (traduites via mapping_logique) — tout le reste du
    module travaille uniquement avec ces noms logiques, jamais avec les
    en-têtes réels du Sheet. Une colonne logique optionnelle et absente du
    Sheet vaut simplement "" dans chaque ligne retournée (jamais une erreur)."""
    rows_bruts = _fetch_raw_rows(sheet_id, label)

    if not rows_bruts:
        logger.warning("[SHEETS WARNING] Sheet %s vide ou sans données.", label)
        return []

    en_tetes_reels = list(rows_bruts[0].keys())
    resolues = _resoudre_colonnes(en_tetes_reels, mapping_logique, label, optionnelles=optionnelles)

    return [
        {
            logique: row.get(resolues[logique], "") if logique in resolues else ""
            for logique in mapping_logique
        }
        for row in rows_bruts
    ]


def _centres_bruts_toutes_sources() -> list[str]:
    """Toutes les valeurs brutes (non normalisées) de la colonne centre,
    élèves ET personnel confondus — base de la dérivation dynamique des
    centres (voir get_centres_derives). Best-effort : une source
    injoignable est ignorée ici (get_eleves()/get_personnel() remonteront
    l'erreur de leur côté si on les appelle directement)."""
    valeurs: list[str] = []
    try:
        for row in _fetch_sheet_rows(settings.google_sheet_eleves_id, _COLONNES_ELEVES, "élèves"):
            valeurs.append(str(row.get("centre", "")))
    except GoogleSheetsError:
        pass
    try:
        rows = _fetch_sheet_rows(
            settings.google_sheet_personnel_id, _COLONNES_PERSONNEL, "personnel",
            optionnelles=_COLONNES_PERSONNEL_OPTIONNELLES,
        )
        valeurs.extend(str(row.get("centre", "")) for row in rows)
    except GoogleSheetsError:
        pass
    return valeurs


def get_centres_derives() -> dict[str, dict]:
    """Centres réels, dérivés dynamiquement des Sheets (élèves + personnel)
    — remplace l'ancienne liste CENTRES_AUTORISES figée en code. Ajouter un
    centre se fait donc uniquement dans les Sheets : dès qu'il y apparaît
    (élève ou personnel), il est pris en compte, sans toucher au code.

    Retourne {forme_repliee: {"canonique": str, "count": int, "suspect": bool}}
    — voir src.core.centre_normalizer.deriver_centres. Un centre "suspect"
    (vu SEUIL_CENTRE_SUSPECT fois ou moins) n'est jamais bloqué ni corrigé,
    seulement signalé ici et journalisé, pour que le docteur vérifie s'il
    s'agit d'une faute de frappe.

    Mis en cache _CACHE_TTL_SECONDS secondes comme le reste — voir
    clear_cache()."""
    def _calculer() -> dict[str, dict]:
        derives = deriver_centres(_centres_bruts_toutes_sources())
        for info in derives.values():
            if info["suspect"]:
                logger.warning(
                    "[SHEETS WARNING] Centre vu %d fois seulement : %r — faute de frappe "
                    "possible, à vérifier dans le Sheet (rien n'est bloqué).",
                    info["count"], info["canonique"],
                )
        return derives

    return _cached("centres_derives", _calculer)


def _appliquer_centre_canonique(row: dict[str, Any]) -> None:
    """Remplace row["centre"] par sa forme canonique dérivée dynamiquement
    des Sheets (voir get_centres_derives) — ne corrige que des variations
    anodines (casse/accents/espaces), jamais une vraie faute de frappe :
    celle-ci reste sous sa propre forme, simplement signalée comme suspecte
    ailleurs (get_centres_derives), jamais ici ligne par ligne."""
    raw_centre = str(row.get("centre", "")).strip()
    if not raw_centre:
        return
    info = get_centres_derives().get(fold_centre(raw_centre))
    if info is not None:
        row["centre"] = info["canonique"]


def _load_eleves() -> list[dict[str, Any]]:
    rows = _fetch_sheet_rows(settings.google_sheet_eleves_id, _COLONNES_ELEVES, "élèves")

    eleves: list[dict[str, Any]] = []
    for i, row in enumerate(rows, start=2):  # ligne 1 = en-têtes
        nom = str(row.get("nom", "")).strip()
        prenom = str(row.get("prenom", "")).strip()
        contact_clean = _clean_contact_parents(str(row.get("contact_parents", "")))

        if not nom or not prenom or not contact_clean:
            logger.warning(
                "[SHEETS WARNING] Ligne %d du Sheet élèves ignorée (nom=%r, prenom=%r, "
                "contact_parents manquant ou inexploitable).",
                i, nom, prenom,
            )
            continue

        eleve = dict(row)
        # Conserve la série (TleD -> "Tle D") pour l'affichage — le filtre de
        # permission, lui, l'ignore (voir classe_normalizer.meme_niveau).
        classe_normalisee = normalize_classe_avec_serie(row.get("classe"))
        if classe_normalisee is not None:
            eleve["classe"] = classe_normalisee
        eleve["identifiant_hakili"] = build_identifiant_hakili(nom, prenom, contact_clean)
        _appliquer_centre_canonique(eleve)
        eleves.append(eleve)

    return eleves


def _load_personnel() -> list[dict[str, Any]]:
    """Charge tout le personnel (enseignants, responsables, administrateur)
    depuis le Sheet personnel unique — le rôle vient de la colonne "role" de
    chaque ligne, il n'y a plus qu'un seul fichier (voir chantier connexion
    nom+PIN).

    Le Sheet a une ligne par AFFECTATION (centre + classe), pas une ligne
    par personne — une même personne peut y apparaître plusieurs fois. On
    regroupe par (nom, prénom) repliés — voir _cle_nom, qui documente la
    limite connue sur les homonymes — au lieu de l'email (optionnel,
    absent chez la plupart des enseignants actuellement).

    Une cellule classe peut contenir plusieurs valeurs séparées par des
    virgules ("6eme, 5eme") : chacune devient une affectation distincte
    pour cette même ligne (même centre). Une ligne sans classe (responsable,
    administrateur) produit une affectation (centre, None) — jamais filtrée
    par classe (voir user_service.get_accessible_eleves).

    Chaque entrée porte aussi "roles" (liste) — "role" reste le rôle
    PRINCIPAL (première valeur non vide rencontrée, comportement inchangé
    pour une personne à rôle unique) ; "roles" contient TOUS les rôles
    effectifs d'une personne, utilisé pour détecter le double rôle
    (responsable ET enseignant à la fois) sans jamais coder de nom en dur —
    voir la boucle de détection ci-dessous et src/ui/app.py pour le
    sélecteur de casquette qui en résulte."""
    par_personne: dict[str, dict[str, Any]] = {}
    nb_sans_pin = 0

    rows = _fetch_sheet_rows(
        settings.google_sheet_personnel_id, _COLONNES_PERSONNEL, "personnel",
        optionnelles=_COLONNES_PERSONNEL_OPTIONNELLES,
    )
    for i, row in enumerate(rows, start=2):
        row = dict(row)
        _appliquer_centre_canonique(row)

        nom = str(row.get("nom", "")).strip()
        prenom = str(row.get("prenom", "")).strip()
        if not nom or not prenom:
            logger.warning(
                "[SHEETS WARNING] Ligne %d du Sheet personnel ignorée : nom ou "
                "prénom manquant.", i,
            )
            continue

        role_brut = str(row.get("role", "")).strip().lower()
        pin = str(row.get("pin", "")).strip()
        email = str(row.get("email", "")).strip()
        centre = row.get("centre") or ""

        cle = _cle_nom(nom, prenom)
        entree = par_personne.setdefault(cle, {
            "nom": nom, "prenom": prenom, "role": "", "pin": "", "email": "",
            "affectations": [], "_roles_bruts": set(), "_centres_responsable": set(),
        })
        if not entree["role"] and role_brut:
            entree["role"] = role_brut
        if role_brut:
            entree["_roles_bruts"].add(role_brut)
        if role_brut == _ROLE_RESPONSABLE and centre:
            # Centre où cette LIGNE porte le rôle responsable — retenu
            # indépendamment de la présence d'une classe sur cette même
            # ligne : dans les données réelles, une ligne responsable porte
            # presque toujours aussi une classe (voir chantier double rôle,
            # bug corrigé). L'accès de la casquette Responsable doit se
            # baser sur le RÔLE de la ligne, jamais sur l'absence de classe.
            entree["_centres_responsable"].add(centre)
        if not entree["pin"] and pin:
            entree["pin"] = pin
        if not entree["email"] and email:
            entree["email"] = email

        classes_normalisees = [
            n for n in (normalize_classe(c) for c in str(row.get("classe", "")).split(","))
            if n
        ]
        if classes_normalisees:
            for classe in classes_normalisees:
                affectation = (centre, classe)
                if affectation not in entree["affectations"]:
                    entree["affectations"].append(affectation)
        else:
            affectation = (centre, None)
            if affectation not in entree["affectations"]:
                entree["affectations"].append(affectation)

    for entree in par_personne.values():
        # Double rôle : détecté par la RÈGLE GÉNÉRALE (jamais par une liste
        # de noms) — soit ses lignes portent littéralement les deux valeurs
        # de rôle, soit elle est déclarée responsable et possède au moins
        # une affectation avec une classe (donc enseigne aussi). Toute
        # nouvelle personne remplissant ce critère obtient "roles" à deux
        # entrées automatiquement, sans modification de code (voir chantier
        # sélecteur de casquette).
        roles_bruts = entree.pop("_roles_bruts")
        entree["centres_responsable"] = sorted(entree.pop("_centres_responsable"))
        a_affectation_enseignement = any(
            classe is not None for _centre, classe in entree["affectations"]
        )
        roles_effectifs = set(roles_bruts)
        if _ROLE_RESPONSABLE in roles_bruts and a_affectation_enseignement:
            roles_effectifs.add(_ROLE_ENSEIGNANT)
        entree["roles"] = sorted(roles_effectifs)

        if not entree["pin"]:
            nb_sans_pin += 1

    if nb_sans_pin:
        logger.warning(
            "[SHEETS WARNING] %d personne(s) du personnel sans PIN — chargée(s) mais ne "
            "pourront pas se connecter (visibles quand même dans la vue Personnel).",
            nb_sans_pin,
        )

    return list(par_personne.values())


def get_eleves() -> list[dict[str, Any]]:
    """Retourne la liste des élèves (Sheet élèves), une entrée par élève
    valide, chacune enrichie du champ calculé 'identifiant_hakili'.

    Une ligne sans nom, prénom ou contact_parents exploitable est ignorée
    (avertissement journalisé) plutôt que de faire échouer tout le
    chargement ou de produire un identifiant ambigu/collisionnable.

    Résultat mis en cache _CACHE_TTL_SECONDS secondes — voir clear_cache().
    En cas de coupure réseau, sert la dernière lecture réussie si elle
    existe (voir _cached_avec_repli, get_statut_lecture) plutôt que de
    lever une exception — jamais en cas d'erreur de configuration.
    """
    return _cached_avec_repli("eleves", _load_eleves)


def get_personnel() -> list[dict[str, Any]]:
    """Retourne la liste de tout le personnel (enseignants, responsables,
    administrateur), lu depuis le Sheet personnel unique
    (GOOGLE_SHEET_PERSONNEL_ID) — le rôle vient de la colonne "role" de
    chaque ligne. Chaque entrée porte 'affectations' : liste de tuples
    (centre, classe) — classe=None pour un responsable/administrateur, qui
    n'est jamais filtré par classe (voir user_service.get_accessible_eleves).

    Une personne sans PIN est chargée quand même (visible dans les listes de
    personnel) mais ne pourra pas se connecter — voir
    src.services.auth_service.

    En cas de coupure réseau, sert la dernière lecture réussie si elle
    existe (voir _cached_avec_repli, get_statut_lecture) plutôt que de
    lever une exception — jamais en cas d'erreur de configuration."""
    return _cached_avec_repli("personnel", _load_personnel)


def get_eleve_by_identifiant(identifiant: str) -> dict[str, Any] | None:
    """Retourne l'élève dont identifiant_hakili correspond exactement, ou
    None si aucun élève ne correspond."""
    for eleve in get_eleves():
        if eleve["identifiant_hakili"] == identifiant:
            return eleve
    return None
