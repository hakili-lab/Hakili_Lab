"""
Tests du mode « accès libre ».

Ce mode ouvre l'application sans connexion pour permettre de travailler avant que
les Google Sheets soient configurés. Il est **verrouillé sur DEBUG**, et ces tests
sont là pour que ce verrou ne saute jamais par accident : l'application porte des
données scolaires nominatives d'élèves mineurs, et une URL publique sans contrôle
d'accès les exposerait à quiconque connaît l'adresse.
"""
from __future__ import annotations

from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(ACCES_LIBRE=True)
class TestAccesLibreActif(TestCase):
    def test_suivi_accessible_sans_connexion(self) -> None:
        reponse = self.client.get(reverse("suivi_web:accueil"))
        self.assertEqual(reponse.status_code, 200)

    def test_correction_accessible_sans_connexion(self) -> None:
        reponse = self.client.get(reverse("correction_web:nouvelle"))
        self.assertEqual(reponse.status_code, 200)

    def test_statistiques_accessibles_sans_connexion(self) -> None:
        """Vue réservée aux administrateurs en temps normal."""
        reponse = self.client.get(reverse("suivi_web:statistiques"))
        self.assertEqual(reponse.status_code, 200)

    def test_bandeau_visible_sur_chaque_page(self) -> None:
        """Une application ouverte sur des données d'élèves ne doit jamais
        pouvoir se faire oublier."""
        for url in (
            reverse("suivi_web:accueil"),
            reverse("correction_web:nouvelle"),
            reverse("correction_web:sujets"),
        ):
            self.assertContains(self.client.get(url), "Accès libre activé")

    def test_bouton_quitter_masque(self) -> None:
        """Il n'y a pas de session à quitter : proposer le bouton laisserait
        croire qu'on est connecté."""
        reponse = self.client.get(reverse("suivi_web:accueil"))
        self.assertNotContains(reponse, "Quitter")


class TestAccesLibreInactif(TestCase):
    """Comportement par défaut : le contrôle d'accès s'applique."""

    def test_suivi_exige_une_connexion(self) -> None:
        reponse = self.client.get(reverse("suivi_web:accueil"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn("/connexion/", reponse["Location"])

    def test_correction_exige_une_connexion(self) -> None:
        reponse = self.client.get(reverse("correction_web:nouvelle"))
        self.assertEqual(reponse.status_code, 302)

    def test_aucun_bandeau(self) -> None:
        self.assertNotContains(
            self.client.get(reverse("comptes:connexion")), "Accès libre activé"
        )


class TestVerrouSurDebug(TestCase):
    """Le verrou qui compte : hors DEBUG, le réglage doit être inopérant."""

    def test_acces_libre_ignore_hors_debug(self) -> None:
        import importlib
        import os
        from unittest.mock import patch

        # On recharge le module de configuration avec la variable présente et
        # DEBUG absent — exactement la situation d'un déploiement où quelqu'un
        # aurait laissé traîner le réglage.
        with patch.dict(
            os.environ,
            {
                "HAKILI_ACCES_LIBRE": "true",
                "DEBUG": "false",
                "DJANGO_SECRET_KEY": "x" * 60,
                "DJANGO_ALLOWED_HOSTS": "exemple.test",
            },
            clear=False,
        ):
            settings_module = importlib.import_module("hakili.settings")
            recharge = importlib.reload(settings_module)
            try:
                self.assertFalse(recharge.DEBUG)
                self.assertFalse(
                    recharge.ACCES_LIBRE,
                    "HAKILI_ACCES_LIBRE ne doit JAMAIS être actif hors DEBUG : "
                    "l'application exposerait des données nominatives d'élèves "
                    "mineurs à toute personne connaissant l'URL.",
                )
            finally:
                # Rétablir la configuration de test pour les tests suivants.
                importlib.reload(settings_module)

    def test_acces_libre_actif_en_debug(self) -> None:
        import importlib
        import os
        from unittest.mock import patch

        with patch.dict(
            os.environ, {"HAKILI_ACCES_LIBRE": "true", "DEBUG": "true"}, clear=False
        ):
            settings_module = importlib.import_module("hakili.settings")
            recharge = importlib.reload(settings_module)
            try:
                self.assertTrue(recharge.ACCES_LIBRE)
            finally:
                importlib.reload(settings_module)
