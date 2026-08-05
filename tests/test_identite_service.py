"""
Tests de `src/services/identite_service.py`.

Cette logique vivait dans l'ancienne interface Streamlit et n'était donc pas
testable : le fichier construisait la configuration au chargement. Ces tests
sont écrits au moment de l'extraction, pour figer le comportement existant avant
que les vues Django ne s'appuient dessus.
"""
from __future__ import annotations

import pytest

from src.core.roles import UserRole
from src.services.identite_service import (
    apparier_eleve_par_nom_fichier,
    casquette_par_defaut,
    correspond_recherche,
    filtrer_par_recherche,
    fold_texte,
    fold_token,
    nom_fichier_document,
    roles_valides_de,
    vue_utilisateur_pour_casquette,
)


# ── Rôles ─────────────────────────────────────────────────────────────────────

def test_roles_depuis_la_liste_roles() -> None:
    personne = {"roles": ["responsable", "enseignant"]}
    assert roles_valides_de(personne) == ["responsable", "enseignant"]


def test_repli_sur_role_unique_si_roles_absent() -> None:
    assert roles_valides_de({"role": "enseignant"}) == ["enseignant"]


def test_role_inconnu_ignore_sans_planter() -> None:
    """Un rôle mal saisi dans le Sheet ne doit pas casser l'aiguillage —
    l'erreur claire est montrée à la connexion."""
    personne = {"roles": ["enseignant", "directeur-adjoint"]}
    assert roles_valides_de(personne) == ["enseignant"]


def test_aucun_role_reconnu() -> None:
    assert roles_valides_de({"roles": ["inconnu"]}) == []
    assert roles_valides_de({}) == []


def test_casquette_par_defaut_privilegie_admin() -> None:
    """Depuis que le périmètre élève est unique (centre d'encadrement, pas école),
    le rôle ne commande plus que l'accès à l'administration : cacher ses propres
    écrans à un administrateur n'aurait pas de sens."""
    assert casquette_par_defaut(["enseignant", "administrateur"]) == "administrateur"
    assert casquette_par_defaut(["enseignant", "responsable"]) == "enseignant"
    assert casquette_par_defaut(["enseignant"]) == "enseignant"
    assert casquette_par_defaut([]) == ""


# ── Casquettes ────────────────────────────────────────────────────────────────

def test_casquette_pose_le_role_sans_filtrer() -> None:
    """Les affectations sont conservées telles quelles : elles sont informatives
    depuis que toute personne autorisée accède à tous les élèves."""
    personne = {
        "role": "enseignant",
        "affectations": [("Tampouy", "3e"), ("Tampouy", None), ("Siao", "4e")],
        "centres_responsable": [],
    }
    vue = vue_utilisateur_pour_casquette(personne, "enseignant")
    assert vue["role_enum"] == UserRole.enseignant
    assert vue["affectations"] == personne["affectations"]



def test_casquette_responsable_ne_restreint_plus() -> None:
    personne = {
        "role": "responsable",
        "affectations": [("Tampouy", "3e")],
        "centres_responsable": ["Tampouy"],
    }
    vue = vue_utilisateur_pour_casquette(personne, "responsable")
    assert vue["role_enum"] == UserRole.responsable_centre
    assert vue["affectations"] == [("Tampouy", "3e")]



def test_casquette_ne_modifie_pas_la_personne_source() -> None:
    personne = {"role": "enseignant", "affectations": [("Tampouy", "3e")]}
    vue_utilisateur_pour_casquette(personne, "enseignant")
    assert "role_enum" not in personne


def test_casquette_admin_ne_touche_pas_aux_affectations() -> None:
    personne = {"role": "administrateur", "affectations": [("Siao", "6e")]}
    vue = vue_utilisateur_pour_casquette(personne, "administrateur")
    assert vue["role_enum"] == UserRole.admin
    assert vue["affectations"] == [("Siao", "6e")]


# ── Recherche ─────────────────────────────────────────────────────────────────

def test_recherche_insensible_a_l_ordre_des_mots() -> None:
    """Bug déjà corrigé une fois : une recherche « Nom Prénom » ne retrouvait pas
    un élève affiché « Prénom Nom »."""
    assert correspond_recherche("Sanou Feryel", "Feryel SANOU")
    assert correspond_recherche("Feryel Sanou", "Feryel SANOU")


def test_recherche_insensible_casse_et_accents() -> None:
    assert correspond_recherche("KABRE", "Kabré Charles")
    assert correspond_recherche("kabre charles", "KABRÉ Charles Eliel")


def test_recherche_vide_correspond_toujours() -> None:
    assert correspond_recherche("", "n'importe qui")
    assert correspond_recherche("   ", "n'importe qui")


def test_recherche_ne_correspond_pas_a_autre_chose() -> None:
    assert not correspond_recherche("Zongo", "Feryel SANOU")


def test_filtrer_par_recherche() -> None:
    eleves = [
        {"nom": "SANOU", "prenom": "Feryel"},
        {"nom": "ZONGO", "prenom": "Ibrahim"},
        {"nom": "KABRE", "prenom": "Charles"},
    ]
    libelle = lambda e: f"{e['prenom']} {e['nom']}"  # noqa: E731
    assert len(filtrer_par_recherche(eleves, "sanou feryel", libelle)) == 1
    assert len(filtrer_par_recherche(eleves, "", libelle)) == 3
    assert filtrer_par_recherche(eleves, "inexistant", libelle) == []


def test_fold_token_et_fold_texte() -> None:
    assert fold_token("KABRÉ Charles") == "kabrecharles"
    assert fold_texte("KABRÉ Charles") == "kabre charles"


# ── Nommage des documents ─────────────────────────────────────────────────────

def test_nom_fichier_document() -> None:
    assert (
        nom_fichier_document(nom="Kabré", prenom="Charles Eliel", doc_type="rapport", date="2026-07-30")
        == "KABRE_Charles_Eliel_rapport_2026-07-30"
    )


def test_nom_fichier_document_sans_identite_exploitable() -> None:
    assert nom_fichier_document(nom="", prenom="", doc_type="scan", date="2026-07-30") == (
        "eleve_scan_2026-07-30"
    )


def test_nom_fichier_document_ne_contient_jamais_de_donnee_sensible() -> None:
    """Ces fichiers circulent par WhatsApp et par mail : ni le numéro du parent
    ni l'identifiant interne ne doivent s'y trouver."""
    nom = nom_fichier_document(
        nom="Kabré", prenom="Charles", doc_type="remediation", date="2026-07-30"
    )
    assert "70" not in nom  # pas de fragment de numéro
    assert "hakili" not in nom.lower()


# ── Appariement batch ─────────────────────────────────────────────────────────

@pytest.fixture
def eleves() -> list[dict]:
    return [
        {"nom": "KABRE", "prenom": "Charles", "identifiant_hakili": "H1"},
        {"nom": "KANAZOE", "prenom": "Rachidatou", "identifiant_hakili": "H2"},
        {"nom": "KANAZOE", "prenom": "Abdoul", "identifiant_hakili": "H3"},
    ]


def test_appariement_nom_et_prenom_presents(eleves) -> None:
    assert apparier_eleve_par_nom_fichier("KABRE_Charles_copie", eleves)["identifiant_hakili"] == "H1"


def test_appariement_insensible_ordre_casse_accents(eleves) -> None:
    assert apparier_eleve_par_nom_fichier("charles-kabré", eleves)["identifiant_hakili"] == "H1"


def test_appariement_refuse_si_nom_seul(eleves) -> None:
    """Deux Kanazoé : le nom de famille seul ne suffit pas à trancher."""
    assert apparier_eleve_par_nom_fichier("KANAZOE_copie", eleves) is None


def test_appariement_refuse_si_introuvable(eleves) -> None:
    assert apparier_eleve_par_nom_fichier("SANOU_Feryel", eleves) is None


def test_appariement_distingue_deux_homonymes_par_le_prenom(eleves) -> None:
    assert (
        apparier_eleve_par_nom_fichier("KANAZOE_Abdoul", eleves)["identifiant_hakili"] == "H3"
    )
