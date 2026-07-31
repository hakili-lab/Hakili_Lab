"""
Tests de l'authentification et du cloisonnement par rôle.

C'est la partie la plus sensible de la migration : le dispositif porte des données
scolaires nominatives d'élèves mineurs. Les scénarios ci-dessous reprennent ceux
qui avaient été vérifiés à la main sur Streamlit (D-CEO-21, D-CEO-24, D-CEO-25) et
les figent.

Le Sheet est simulé : ces tests vérifient les règles d'accès, pas la connectivité
Google.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

_PERSONNEL = [
    {
        "nom": "DIANE", "prenom": "Abasse", "role": "responsable",
        "roles": ["responsable", "enseignant"], "pin": "1234", "email": "",
        "affectations": [("Tampouy", "3e")], "centres_responsable": ["Tampouy"],
    },
    {
        "nom": "SANOU", "prenom": "Feryel", "role": "enseignant",
        "roles": ["enseignant"], "pin": "5678", "email": "",
        "affectations": [("Siao", "4e")], "centres_responsable": [],
    },
    {
        "nom": "ADMIN", "prenom": "Hakili", "role": "administrateur",
        "roles": ["administrateur"], "pin": "9999", "email": "",
        "affectations": [], "centres_responsable": [],
    },
    {
        "nom": "SANSPIN", "prenom": "Personne", "role": "enseignant",
        "roles": ["enseignant"], "pin": "", "email": "",
        "affectations": [("Siao", "4e")], "centres_responsable": [],
    },
    {
        "nom": "ROLEFAUX", "prenom": "Personne", "role": "directeur-adjoint",
        "roles": [], "pin": "4321", "email": "",
        "affectations": [], "centres_responsable": [],
    },
]

_ELEVES = [
    {"nom": "KABRE", "prenom": "Charles", "classe": "3e", "centre": "Tampouy",
     "identifiant_hakili": "HAK-2026-0001", "contact_parents": "70000001"},
    {"nom": "ZONGO", "prenom": "Ibrahim", "classe": "4e", "centre": "Tampouy",
     "identifiant_hakili": "HAK-2026-0002", "contact_parents": "70000002"},
    {"nom": "OUEDRAOGO", "prenom": "Salif", "classe": "4e", "centre": "Siao",
     "identifiant_hakili": "HAK-2026-0003", "contact_parents": "70000003"},
]


def _cle(nom: str, prenom: str) -> str:
    from src.integrations.google_sheets import _cle_nom

    return _cle_nom(nom, prenom)


class BaseAuth(TestCase):
    def setUp(self) -> None:
        self.patch_personnel = patch(
            "src.integrations.google_sheets.get_personnel", return_value=_PERSONNEL
        )
        self.patch_eleves = patch(
            "src.integrations.google_sheets.get_eleves", return_value=_ELEVES
        )
        self.patch_personnel.start()
        self.patch_eleves.start()
        self.addCleanup(self.patch_personnel.stop)
        self.addCleanup(self.patch_eleves.stop)

    def connecter(self, nom: str, prenom: str, pin: str):
        return self.client.post(
            reverse("comptes:connexion"),
            {"cle": _cle(nom, prenom), "pin": pin},
            follow=True,
        )


class TestConnexion(BaseAuth):
    def test_pin_correct_connecte(self) -> None:
        reponse = self.connecter("DIANE", "Abasse", "1234")
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.session["hakili_personne"]["nom"], "DIANE")

    def test_pin_incorrect_refuse(self) -> None:
        reponse = self.connecter("DIANE", "Abasse", "0000")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(reponse, "Code incorrect")

    def test_pin_absent_du_sheet_message_explicite(self) -> None:
        """Un compte sans PIN configuré n'est pas la même erreur qu'un mauvais PIN
        — le message doit renvoyer vers le docteur."""
        reponse = self.connecter("SANSPIN", "Personne", "1234")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(reponse, "Aucun code PIN")

    def test_role_non_reconnu_refuse(self) -> None:
        reponse = self.connecter("ROLEFAUX", "Personne", "4321")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(reponse, "Rôle non reconnu")

    def test_personne_absente_du_sheet_refusee(self) -> None:
        """Le Sheet fait foi : un nom qui n'y est plus ne peut pas se connecter."""
        reponse = self.client.post(
            reverse("comptes:connexion"),
            {"cle": _cle("FANTOME", "Inexistant"), "pin": "1234"},
            follow=True,
        )
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(reponse, "plus dans le Sheet")

    def test_compte_django_sans_mot_de_passe_utilisable(self) -> None:
        """Le PIN reste dans le Sheet. Un mot de passe en base recréerait la
        seconde source de vérité que le projet a démolie deux fois."""
        from django.contrib.auth.models import User

        self.connecter("DIANE", "Abasse", "1234")
        utilisateur = User.objects.get(username=_cle("DIANE", "Abasse"))
        self.assertFalse(utilisateur.has_usable_password())

    def test_admin_recoit_acces_admin_django(self) -> None:
        from django.contrib.auth.models import User

        self.connecter("ADMIN", "Hakili", "9999")
        utilisateur = User.objects.get(username=_cle("ADMIN", "Hakili"))
        self.assertTrue(utilisateur.is_staff)

    def test_enseignant_ne_recoit_pas_acces_admin_django(self) -> None:
        from django.contrib.auth.models import User

        self.connecter("SANOU", "Feryel", "5678")
        utilisateur = User.objects.get(username=_cle("SANOU", "Feryel"))
        self.assertFalse(utilisateur.is_staff)

    def test_deconnexion(self) -> None:
        self.connecter("DIANE", "Abasse", "1234")
        self.client.post(reverse("comptes:deconnexion"))
        self.assertNotIn("_auth_user_id", self.client.session)


class TestAccesProtege(BaseAuth):
    def test_suivi_exige_une_connexion(self) -> None:
        reponse = self.client.get(reverse("suivi_web:accueil"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn("/connexion/", reponse["Location"])

    def test_statistiques_reservees_a_l_admin(self) -> None:
        self.connecter("SANOU", "Feryel", "5678")
        reponse = self.client.get(reverse("suivi_web:statistiques"))
        self.assertEqual(reponse.status_code, 403)

    def test_statistiques_accessibles_a_l_admin(self) -> None:
        self.connecter("ADMIN", "Hakili", "9999")
        with patch("src.db.database.SessionLocal"):
            reponse = self.client.get(reverse("suivi_web:statistiques"))
        self.assertEqual(reponse.status_code, 200)


class TestCasquettes(BaseAuth):
    def test_double_role_demarre_sur_responsable(self) -> None:
        """Vue d'ensemble du centre : point d'entrée jugé le plus sûr."""
        self.connecter("DIANE", "Abasse", "1234")
        self.assertEqual(self.client.session["hakili_casquette"], "responsable")

    def test_changement_de_casquette_autorise(self) -> None:
        self.connecter("DIANE", "Abasse", "1234")
        self.client.post(reverse("comptes:casquette"), {"casquette": "enseignant"})
        self.assertEqual(self.client.session["hakili_casquette"], "enseignant")

    def test_casquette_non_portee_refusee(self) -> None:
        """Sans ce contrôle, une requête forgée élargirait le périmètre de
        quelqu'un à celui d'un administrateur."""
        self.connecter("SANOU", "Feryel", "5678")
        self.client.post(reverse("comptes:casquette"), {"casquette": "administrateur"})
        self.assertEqual(self.client.session["hakili_casquette"], "enseignant")

    def test_changement_de_casquette_refuse_en_get(self) -> None:
        """Un changement de périmètre n'est pas une navigation : il ne doit pas
        pouvoir arriver par un lien cliqué depuis une autre page."""
        self.connecter("DIANE", "Abasse", "1234")
        self.client.get(reverse("comptes:casquette"), {"casquette": "enseignant"})
        self.assertEqual(self.client.session["hakili_casquette"], "responsable")


class TestPerimetreUnique(BaseAuth):
    """Centre d'encadrement, pas école : toute personne autorisée voit tous les
    élèves.

    Le cloisonnement par centre et par classe a été retiré — les enseignants
    tournent et reprennent les copies d'un collègue absent, le filtrage bloquait
    un travail légitime sans rien protéger d'utile. Ce qui protège, c'est
    l'autorisation en amont : présent dans le Sheet avec un code, ou pas.
    """

    def _noms_affiches(self, reponse) -> list[str]:
        contenu = reponse.content.decode()
        return [e["nom"] for e in _ELEVES if e["nom"] in contenu]

    def test_enseignant_voit_tous_les_eleves(self) -> None:
        """Avant : seulement sa classe et son centre."""
        self.connecter("SANOU", "Feryel", "5678")
        reponse = self.client.get(reverse("suivi_web:accueil"))
        self.assertEqual(len(self._noms_affiches(reponse)), 3)

    def test_responsable_voit_tous_les_eleves(self) -> None:
        """Avant : seulement son centre."""
        self.connecter("DIANE", "Abasse", "1234")
        reponse = self.client.get(reverse("suivi_web:accueil"))
        self.assertEqual(len(self._noms_affiches(reponse)), 3)

    def test_admin_voit_tous_les_eleves(self) -> None:
        self.connecter("ADMIN", "Hakili", "9999")
        reponse = self.client.get(reverse("suivi_web:accueil"))
        self.assertEqual(len(self._noms_affiches(reponse)), 3)

    def test_enseignant_accede_au_profil_de_n_importe_quel_eleve(self) -> None:
        """Un enseignant récupérant les copies d'un collègue absent ne doit pas
        être bloqué."""
        from suivi_web.jetons import jeton_eleve

        self.connecter("SANOU", "Feryel", "5678")  # Siao / 4e
        reponse = self.client.get(
            reverse("suivi_web:eleve_detail", args=[jeton_eleve("HAK-2026-0001")])
        )  # élève de Tampouy / 3e
        self.assertEqual(reponse.status_code, 200)

    def test_administration_reste_reservee(self) -> None:
        """Le rôle ne commande plus le périmètre élève, mais toujours l'accès à
        l'administration."""
        self.connecter("SANOU", "Feryel", "5678")
        self.assertEqual(
            self.client.get(reverse("suivi_web:statistiques")).status_code, 403
        )

    def test_administration_ouverte_a_l_admin(self) -> None:
        from unittest.mock import patch

        self.connecter("ADMIN", "Hakili", "9999")
        with patch("src.db.database.SessionLocal"):
            self.assertEqual(
                self.client.get(reverse("suivi_web:statistiques")).status_code, 200
            )

    def test_aucune_donnee_sensible_a_l_ecran(self) -> None:
        self.connecter("ADMIN", "Hakili", "9999")
        contenu = self.client.get(reverse("suivi_web:accueil")).content.decode()
        for eleve in _ELEVES:
            self.assertNotIn(eleve["contact_parents"], contenu)
            self.assertNotIn(eleve["identifiant_hakili"], contenu)

    def test_recherche_insensible_a_l_ordre_des_mots(self) -> None:
        self.connecter("ADMIN", "Hakili", "9999")
        reponse = self.client.get(reverse("suivi_web:accueil"), {"q": "charles kabre"})
        self.assertEqual(self._noms_affiches(reponse), ["KABRE"])
