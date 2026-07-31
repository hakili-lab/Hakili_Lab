"""
Tests du plan de remédiation.

L'ordre du plan n'est pas cosmétique : travailler les identités remarquables avec
un élève qui ne sait pas additionner deux relatifs est du temps perdu, et le tuteur
ne le découvrirait qu'en séance. C'est ce que ces tests protègent.
"""
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from referentiel.models import Competence, Prerequis, TypeErreur
from suivi.models import EtatProbleme, Probleme, Session
from suivi.plan import construire, ordonner


class BasePlan(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.cpt = TypeErreur.objects.create(
            code="CPT", libelle="Erreur conceptuelle", definition="…",
            signature="…", coefficient=Decimal("0.35"), remediable=True,
        )

        # Chaîne réelle : L.IDR ← L.DEV1 ← N.RELOP
        cls.relop = Competence.objects.create(
            code="N.RELOP", domaine="Activites numeriques",
            libelle="Operations sur les relatifs", niveau_intro="5eme",
            volume_horaire=Decimal("7"),
        )
        cls.dev1 = Competence.objects.create(
            code="L.DEV1", domaine="Calcul litteral et algebre",
            libelle="Developpement et reduction", niveau_intro="5eme",
            volume_horaire=Decimal("4.5"),
        )
        cls.idr = Competence.objects.create(
            code="L.IDR", domaine="Calcul litteral et algebre",
            libelle="Identites remarquables", niveau_intro="4eme",
            volume_horaire=Decimal("2"),
        )
        Prerequis.objects.create(competence=cls.idr, prerequis=cls.dev1)
        Prerequis.objects.create(competence=cls.dev1, prerequis=cls.relop)

    def _session(self, competences, cout="1") -> Session:
        session = Session.objects.create(identifiant_hakili="HAK-PLAN")
        for competence in competences:
            Probleme.objects.create(
                session=session, competence=competence, type_erreur=self.cpt,
                cout_estime=Decimal(cout),
            ).changer_etat(EtatProbleme.CONFIRME)
        return session


class TestOrdonnancement(BasePlan):
    def test_un_prerequis_en_difficulte_passe_avant(self) -> None:
        """Le cœur du plan : on remonte à la cause avant de traiter le symptôme."""
        session = self._session([self.idr, self.dev1, self.relop])
        codes = [e.competence.code for e in construire(session)["etapes"]]
        self.assertEqual(codes, ["N.RELOP", "L.DEV1", "L.IDR"])

    def test_ordre_independant_de_la_saisie(self) -> None:
        """Quel que soit l'ordre de détection, le plan sort le même."""
        session = self._session([self.relop, self.idr, self.dev1])
        codes = [e.competence.code for e in construire(session)["etapes"]]
        self.assertEqual(codes, ["N.RELOP", "L.DEV1", "L.IDR"])

    def test_prerequis_hors_difficulte_ignore(self) -> None:
        """N.RELOP n'est pas un problème : L.DEV1 n'a rien à attendre."""
        session = self._session([self.idr, self.dev1])
        etapes = construire(session)["etapes"]
        self.assertEqual([e.competence.code for e in etapes], ["L.DEV1", "L.IDR"])
        self.assertEqual(etapes[0].prerequis_aussi_en_difficulte, [])

    def test_les_prerequis_bloquants_sont_signales(self) -> None:
        session = self._session([self.idr, self.dev1])
        derniere = construire(session)["etapes"][-1]
        self.assertEqual(
            [c.code for c in derniere.prerequis_aussi_en_difficulte], ["L.DEV1"]
        )

    def test_a_egalite_le_plus_fondamental_dabord(self) -> None:
        """Deux compétences sans lien : celle introduite le plus tôt passe avant."""
        tot = Competence.objects.create(
            code="N.NUM", domaine="Activites numeriques", libelle="Numeration",
            niveau_intro="Primaire", volume_horaire=Decimal("2"),
        )
        session = self._session([self.idr, tot])
        codes = [e.competence.code for e in construire(session)["etapes"]]
        self.assertEqual(codes[0], "N.NUM")

    def test_un_cycle_ne_fait_pas_boucler(self) -> None:
        """La base interdit les cycles, mais un import mal formé pourrait en créer
        un : mieux vaut un ordre imparfait qu'une boucle infinie."""
        a = Competence.objects.create(
            code="C.A", domaine="Activites numeriques", libelle="A",
            niveau_intro="6eme", volume_horaire=Decimal("2"),
        )
        b = Competence.objects.create(
            code="C.B", domaine="Activites numeriques", libelle="B",
            niveau_intro="6eme", volume_horaire=Decimal("2"),
        )
        Prerequis.objects.create(competence=a, prerequis=b)
        Prerequis.objects.create(competence=b, prerequis=a)

        session = self._session([a, b])
        self.assertEqual(len(construire(session)["etapes"]), 2)

    def test_liste_vide(self) -> None:
        self.assertEqual(ordonner([]), [])


class TestContenuDuPlan(BasePlan):
    def test_total_et_palier(self) -> None:
        session = self._session([self.idr, self.dev1], cout="5")
        plan = construire(session)
        self.assertEqual(plan["total_heures"], Decimal("10"))
        self.assertEqual(plan["palier"], "B")
        self.assertEqual(plan["nb_problemes"], 2)

    def test_les_hypotheses_ne_sont_pas_dans_le_plan(self) -> None:
        """Une lacune non vérifiée n'a rien à faire dans un plan de travail —
        c'est tout l'objet du test de confirmation."""
        session = Session.objects.create(identifiant_hakili="HAK-HYP")
        Probleme.objects.create(
            session=session, competence=self.idr, type_erreur=self.cpt,
            cout_estime=Decimal("2"),
        )  # reste en hypothèse
        self.assertEqual(construire(session)["etapes"], [])

    def test_les_problemes_en_remediation_restent_au_plan(self) -> None:
        """Après inscription, le tuteur doit toujours voir sa feuille de route."""
        session = self._session([self.idr])
        session.inscrire()
        self.assertEqual(len(construire(session)["etapes"]), 1)

    def test_volume_estime_signale(self) -> None:
        """Un volume de repli ne doit pas passer pour un chiffre officiel : c'est
        lui qui détermine ce qu'une famille paiera."""
        lycee = Competence.objects.create(
            code="F.DER", domaine="Fonctions et applications", libelle="Derivation",
            niveau_intro="1ereD", volume_horaire=Decimal("4"), volume_estime=True,
        )
        session = self._session([lycee])
        self.assertTrue(construire(session)["repose_sur_estimation"])

    def test_pas_de_signalement_si_volumes_officiels(self) -> None:
        session = self._session([self.idr])
        self.assertFalse(construire(session)["repose_sur_estimation"])
