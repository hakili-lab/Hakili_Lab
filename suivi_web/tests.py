"""
Tests des vues de suivi : profil d'un élève et accès aux documents.

Le point le plus important est `TestAccesDocuments` : un document est une copie
d'élève, et l'autorisation doit être vérifiée sur l'URL du document lui-même, pas
seulement sur la page qui affiche le lien. Sans cela une URL devinée ou partagée
suffirait à récupérer la copie d'un élève d'un autre centre.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from comptes.tests import _ELEVES, _PERSONNEL, _cle
from suivi_web.jetons import identifiant_depuis_jeton, jeton_eleve

_PDF = b"%PDF-1.4 faux document de test"


def _copie(copy_id: str, identifiant: str, note=12.0):
    return SimpleNamespace(
        copy_id=copy_id,
        identifiant_hakili=identifiant,
        classe="3e",
        annee_scolaire="2026",
        date_soumission=date(2026, 5, 12),
        notes_finales=note,
    )


class BaseSuivi(TestCase):
    def setUp(self) -> None:
        for cible, valeur in (
            ("get_personnel", _PERSONNEL),
            ("get_eleves", _ELEVES),
        ):
            correctif = patch(
                f"src.integrations.google_sheets.{cible}", return_value=valeur
            )
            correctif.start()
            self.addCleanup(correctif.stop)

        correctif_eleve = patch(
            "src.integrations.google_sheets.get_eleve_by_identifiant",
            side_effect=lambda ident: next(
                (e for e in _ELEVES if e["identifiant_hakili"] == ident), None
            ),
        )
        correctif_eleve.start()
        self.addCleanup(correctif_eleve.stop)

        # La base n'est pas jointe : ces tests portent sur les autorisations.
        correctif_copies = patch(
            "src.services.copie_service.get_copies_pour_identifiants", return_value={}
        )
        correctif_copies.start()
        self.addCleanup(correctif_copies.stop)

        correctif_hist = patch(
            "src.services.copie_service.get_historique_eleve", return_value=[]
        )
        correctif_hist.start()
        self.addCleanup(correctif_hist.stop)

        correctif_session = patch("src.db.database.SessionLocal")
        correctif_session.start()
        self.addCleanup(correctif_session.stop)

    def connecter(self, nom: str, prenom: str, pin: str):
        return self.client.post(
            reverse("comptes:connexion"), {"cle": _cle(nom, prenom), "pin": pin}, follow=True
        )


class TestJetons(TestCase):
    def test_aller_retour(self) -> None:
        self.assertEqual(identifiant_depuis_jeton(jeton_eleve("HAK-2026-0001")), "HAK-2026-0001")

    def test_jeton_forge_rejete(self) -> None:
        self.assertIsNone(identifiant_depuis_jeton("nimportequoi"))

    def test_jeton_altere_rejete(self) -> None:
        jeton = jeton_eleve("HAK-2026-0001")
        altere = jeton[:-3] + ("aaa" if not jeton.endswith("aaa") else "bbb")
        self.assertIsNone(identifiant_depuis_jeton(altere))

    def test_le_jeton_ne_contient_pas_l_identifiant_en_clair(self) -> None:
        """C'est tout l'objet : `identifiant_hakili` ne doit apparaître ni dans
        l'URL, ni dans l'historique du navigateur, ni dans les journaux."""
        self.assertNotIn("HAK-2026-0001", jeton_eleve("HAK-2026-0001"))


class TestProfilEleve(BaseSuivi):
    def test_responsable_accede_a_un_eleve_de_son_centre(self) -> None:
        self.connecter("DIANE", "Abasse", "1234")
        reponse = self.client.get(
            reverse("suivi_web:eleve_detail", args=[jeton_eleve("HAK-2026-0001")])
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "KABRE")

    def test_acces_ouvert_a_toute_personne_autorisee(self) -> None:
        """Centre d'encadrement : un enseignant de Siao accède à un élève de
        Tampouy. Le cloisonnement par centre et classe a été retiré — il bloquait
        un enseignant reprenant les copies d'un collègue absent."""
        self.connecter("SANOU", "Feryel", "5678")
        reponse = self.client.get(
            reverse("suivi_web:eleve_detail", args=[jeton_eleve("HAK-2026-0001")])
        )
        self.assertEqual(reponse.status_code, 200)

    def test_eleve_inconnu_donne_404(self) -> None:
        self.connecter("ADMIN", "Hakili", "9999")
        reponse = self.client.get(
            reverse("suivi_web:eleve_detail", args=[jeton_eleve("INEXISTANT")])
        )
        self.assertEqual(reponse.status_code, 404)

    def test_jeton_invalide_donne_404(self) -> None:
        self.connecter("ADMIN", "Hakili", "9999")
        reponse = self.client.get(reverse("suivi_web:eleve_detail", args=["forge"]))
        self.assertEqual(reponse.status_code, 404)

    def test_profil_exige_une_connexion(self) -> None:
        reponse = self.client.get(
            reverse("suivi_web:eleve_detail", args=[jeton_eleve("HAK-2026-0001")])
        )
        self.assertEqual(reponse.status_code, 302)
        self.assertIn("/connexion/", reponse["Location"])

    def test_aucune_donnee_sensible_sur_le_profil(self) -> None:
        self.connecter("ADMIN", "Hakili", "9999")
        contenu = self.client.get(
            reverse("suivi_web:eleve_detail", args=[jeton_eleve("HAK-2026-0001")])
        ).content.decode()
        self.assertNotIn("70000001", contenu)  # contact_parents
        self.assertNotIn("HAK-2026-0001", contenu)        # identifiant_hakili


class TestEcranParcours(BaseSuivi):
    """Le plan de remédiation et le bouton d'inscription."""

    def setUp(self) -> None:
        super().setUp()
        from decimal import Decimal

        from referentiel.models import Competence, Prerequis, TypeErreur
        from suivi.models import EtatProbleme, Probleme, Session

        cpt = TypeErreur.objects.create(
            code="CPT", libelle="Erreur conceptuelle", definition="…",
            signature="…", coefficient=Decimal("0.35"), remediable=True,
        )
        dev1 = Competence.objects.create(
            code="L.DEV1", domaine="Calcul litteral et algebre",
            libelle="Developpement et reduction", niveau_intro="5eme",
            volume_horaire=Decimal("4.5"),
        )
        idr = Competence.objects.create(
            code="L.IDR", domaine="Calcul litteral et algebre",
            libelle="Identites remarquables", niveau_intro="4eme",
            volume_horaire=Decimal("2"),
        )
        Prerequis.objects.create(competence=idr, prerequis=dev1)

        self.session = Session.objects.create(identifiant_hakili="HAK-2026-0001")
        for competence in (idr, dev1):
            Probleme.objects.create(
                session=self.session, competence=competence, type_erreur=cpt,
                cout_estime=Decimal("2"),
            ).changer_etat(EtatProbleme.CONFIRME)
        self.session.etablir_le_plan()
        self.jeton = jeton_eleve(str(self.session.pk))

    def _url(self, nom: str = "session_detail") -> str:
        return reverse(f"suivi_web:{nom}", args=[self.jeton])

    def test_le_plan_est_ordonne_par_prerequis(self) -> None:
        self.connecter("DIANE", "Abasse", "1234")
        contenu = self.client.get(self._url()).content.decode()
        self.assertLess(
            contenu.index("Developpement et reduction"),
            contenu.index("Identites remarquables"),
        )

    def test_le_volume_et_le_palier_sont_affiches(self) -> None:
        self.connecter("DIANE", "Abasse", "1234")
        reponse = self.client.get(self._url())
        self.assertContains(reponse, "4 h")
        self.assertContains(reponse, "Inscrire au programme")

    def test_inscription_depuis_l_ecran(self) -> None:
        self.connecter("DIANE", "Abasse", "1234")
        self.client.post(self._url("inscrire"))

        self.session.refresh_from_db()
        self.assertTrue(self.session.inscrite)
        self.assertIsNotNone(self.session.date_inscription)

    def test_inscription_refusee_en_get(self) -> None:
        """Une inscription engage un volume horaire et une facturation : elle ne
        doit pas pouvoir arriver par un lien cliqué ailleurs."""
        self.connecter("DIANE", "Abasse", "1234")
        self.client.get(self._url("inscrire"))
        self.session.refresh_from_db()
        self.assertFalse(self.session.inscrite)

    def test_inscription_exige_une_connexion(self) -> None:
        reponse = self.client.post(self._url("inscrire"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn("/connexion/", reponse["Location"])

    def test_bouton_disparait_une_fois_inscrit(self) -> None:
        self.connecter("DIANE", "Abasse", "1234")
        self.client.post(self._url("inscrire"))
        reponse = self.client.get(self._url())
        self.assertNotContains(reponse, "Inscrire au programme")

    def test_palier_c_demande_un_motif(self) -> None:
        from decimal import Decimal

        from referentiel.models import Competence, TypeErreur
        from suivi.models import EtatProbleme, Probleme, Session

        cpt = TypeErreur.objects.get(code="CPT")
        session = Session.objects.create(identifiant_hakili="HAK-2026-0001")
        for i in range(12):
            competence = Competence.objects.create(
                code=f"Z.{i}", domaine="Activites numeriques", libelle=f"Z{i}",
                niveau_intro="4eme", volume_horaire=Decimal("4"),
            )
            Probleme.objects.create(
                session=session, competence=competence, type_erreur=cpt,
                cout_estime=Decimal("2"),
            ).changer_etat(EtatProbleme.CONFIRME)
        session.etablir_le_plan()
        jeton = jeton_eleve(str(session.pk))

        self.connecter("DIANE", "Abasse", "1234")
        reponse = self.client.get(reverse("suivi_web:session_detail", args=[jeton]))
        self.assertContains(reponse, "Palier C")
        self.assertContains(reponse, "Motif de la dérogation")

        # Sans motif : refusé.
        self.client.post(reverse("suivi_web:inscrire", args=[jeton]), {"forcer": "1"})
        session.refresh_from_db()
        self.assertFalse(session.inscrite)

        # Avec motif : accepté et tracé.
        self.client.post(
            reverse("suivi_web:inscrire", args=[jeton]),
            {"forcer": "1", "motif": "Accord écrit de la famille"},
        )
        session.refresh_from_db()
        self.assertTrue(session.inscrite)
        derniere = session.problemes.first().transitions.order_by("-pk").first()
        self.assertIn("Accord écrit de la famille", derniere.commentaire)

    def test_parcours_hors_perimetre_donne_404(self) -> None:
        self.connecter("DIANE", "Abasse", "1234")
        reponse = self.client.get(
            reverse("suivi_web:session_detail", args=[jeton_eleve("99999")])
        )
        self.assertEqual(reponse.status_code, 404)


class TestVuePersonnel(BaseSuivi):
    """L'admin doit voir qui a accès — et surtout qui ne l'a pas."""

    def test_reservee_a_l_administrateur(self) -> None:
        self.connecter("SANOU", "Feryel", "5678")
        self.assertEqual(
            self.client.get(reverse("suivi_web:personnel")).status_code, 403
        )

    def test_liste_tout_le_personnel(self) -> None:
        self.connecter("ADMIN", "Hakili", "9999")
        reponse = self.client.get(reverse("suivi_web:personnel"))
        self.assertEqual(reponse.status_code, 200)
        for personne in _PERSONNEL:
            self.assertContains(reponse, personne["nom"])

    def test_personne_sans_code_signalee_et_non_masquee(self) -> None:
        """Elle figure dans le Sheet en croyant avoir accès, et ne peut pas se
        connecter : c'est exactement ce que l'admin doit voir."""
        self.connecter("ADMIN", "Hakili", "9999")
        reponse = self.client.get(reverse("suivi_web:personnel"))
        self.assertContains(reponse, "SANSPIN")
        self.assertContains(reponse, "Aucun code")

    def test_role_non_reconnu_signale(self) -> None:
        self.connecter("ADMIN", "Hakili", "9999")
        reponse = self.client.get(reverse("suivi_web:personnel"))
        self.assertContains(reponse, "ROLEFAUX")
        self.assertContains(reponse, "non reconnu")

    def test_renvoie_vers_le_sheet_pour_modifier(self) -> None:
        """Aucune modification ici : le Sheet fait foi (D-CEO-21)."""
        self.connecter("ADMIN", "Hakili", "9999")
        reponse = self.client.get(reverse("suivi_web:personnel"))
        self.assertContains(reponse, "dans le Google Sheet")

    def test_aucun_code_d_acces_affiche(self) -> None:
        """Le PIN est en clair dans le Sheet ; il n'a rien à faire à l'écran."""
        self.connecter("ADMIN", "Hakili", "9999")
        contenu = self.client.get(reverse("suivi_web:personnel")).content.decode()
        for personne in _PERSONNEL:
            if personne["pin"]:
                self.assertNotIn(personne["pin"], contenu)


class TestAccesDocuments(BaseSuivi):
    """L'autorisation doit être revérifiée sur l'URL du document."""

    def setUp(self) -> None:
        super().setUp()
        self.copie = _copie("copie-H1", "HAK-2026-0001")
        self.doc = SimpleNamespace(type="rapport", fichier=_PDF)

        correctif_copie = patch(
            "src.services.copie_service.get_copie_by_id", return_value=self.copie
        )
        correctif_copie.start()
        self.addCleanup(correctif_copie.stop)

        correctif_doc = patch(
            "src.services.copie_service.get_document_by_type", return_value=self.doc
        )
        correctif_doc.start()
        self.addCleanup(correctif_doc.stop)

    def _url(self) -> str:
        return reverse(
            "suivi_web:document", args=[jeton_eleve("copie-H1"), "rapport"]
        )

    def test_document_servi_a_qui_y_a_droit(self) -> None:
        self.connecter("DIANE", "Abasse", "1234")
        reponse = self.client.get(self._url())
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse["Content-Type"], "application/pdf")
        self.assertEqual(reponse.content, _PDF)

    def test_document_servi_a_toute_personne_autorisee(self) -> None:
        """Périmètre unique : tout enseignant autorisé accède au document."""
        self.connecter("SANOU", "Feryel", "5678")
        reponse = self.client.get(self._url())
        self.assertEqual(reponse.status_code, 200)

    def test_document_refuse_sans_connexion(self) -> None:
        reponse = self.client.get(self._url())
        self.assertEqual(reponse.status_code, 302)
        self.assertIn("/connexion/", reponse["Location"])

    def test_nom_de_fichier_sans_donnee_sensible(self) -> None:
        """Ces fichiers circulent par WhatsApp et par mail."""
        self.connecter("DIANE", "Abasse", "1234")
        disposition = self.client.get(self._url())["Content-Disposition"]
        self.assertIn("KABRE_Charles_rapport", disposition)
        self.assertNotIn("70000001", disposition)
        self.assertNotIn("HAK-2026-0001", disposition)

    def test_apercu_par_defaut_telechargement_sur_demande(self) -> None:
        self.connecter("DIANE", "Abasse", "1234")
        self.assertIn("inline", self.client.get(self._url())["Content-Disposition"])
        self.assertIn(
            "attachment",
            self.client.get(self._url() + "?telecharger=1")["Content-Disposition"],
        )

    def test_type_reel_detecte_et_non_devine(self) -> None:
        """Un scan peut être une photo, contrairement au rapport toujours en PDF :
        le format est lu dans les octets, pas déduit du champ `type`."""
        self.doc.fichier = b"\xff\xd8\xff\xe0 faux jpeg"
        self.connecter("DIANE", "Abasse", "1234")
        self.assertEqual(self.client.get(self._url())["Content-Type"], "image/jpeg")
