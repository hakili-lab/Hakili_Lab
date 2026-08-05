"""Authentification du personnel (administrateur, responsables, enseignants)
par sélection du nom + code PIN à 4 chiffres.

Le Sheet personnel (src.integrations.google_sheets) est la SEULE source de
vérité pour l'identité, le rôle, les affectations ET le PIN : tout est relu
depuis le Sheet à chaque connexion, jamais stocké en base — PostgreSQL n'a
plus aucune table d'authentification (la table `credentials` a été
supprimée, voir migration correspondante).

Il n'y a plus d'email saisi ni de mot de passe créé/haché : l'utilisateur
choisit son nom dans une liste déroulante (recherchable,
insensible casse/accents) puis saisit son PIN. Le PIN est stocké EN CLAIR
dans le Sheet — choix assumé du docteur (Sheet réservé, pas de sensibilité
bancaire), aucun anti-forçage demandé."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AuthResult:
    """status : "pin_absent" (aucun PIN configuré pour cette personne dans
    le Sheet) | "pin_incorrect" | "ok". personne : dict Sheet (voir
    google_sheets.get_personnel)."""
    status: str
    personne: dict | None = None


def authentifier(personne: dict | None, pin: str) -> AuthResult:
    """Compare le PIN saisi au PIN du Sheet pour la personne déjà
    sélectionnée dans la liste déroulante (le choix du nom fait foi, il n'y
    a plus de vérification d'email ni de rôle déclaré séparément : le rôle
    vient directement de `personne["role"]`, lu dans le Sheet)."""
    if personne is None:
        return AuthResult(status="pin_absent")

    pin_attendu = str(personne.get("pin") or "").strip()
    if not pin_attendu:
        return AuthResult(status="pin_absent", personne=personne)

    if str(pin or "").strip() != pin_attendu:
        return AuthResult(status="pin_incorrect", personne=personne)

    return AuthResult(status="ok", personne=personne)
