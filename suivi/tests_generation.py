"""
Tests de `suivi/generation.py` — sélection des problèmes ciblés par T3/T4/T5
et comportement best-effort de la génération de sujet.

Aucun appel réel au LLM ici : `generer_sujet_verification` est testée avec le
client mocké, comme le module 4/5 existant (`suivi_web.tests.TestConfirmationT1`
teste la mécanique de transition, pas la génération elle-même).
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from referentiel.models import Competence, TypeErreur
from suivi.generation import problemes_a_verifier
from suivi.models import EtatProbleme, Probleme, Session, TypeEvaluation


class BaseGeneration(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.cpt = TypeErreur.objects.create(
            code="CPT", libelle="Erreur conceptuelle", definition="…",
            signature="…", coefficient=Decimal("0.35"), remediable=True,
        )
        cls.idr = Competence.objects.create(
            code="L.IDR", domaine="Calcul litteral et algebre",
            libelle="Identites remarquables", niveau_intro="4eme",
            volume_horaire=Decimal("2"),
        )
        cls.dev1 = Competence.objects.create(
            code="L.DEV1", domaine="Calcul litteral et algebre",
            libelle="Developpement et reduction", niveau_intro="5eme",
            volume_horaire=Decimal("4.5"),
        )

    def setUp(self) -> None:
        self.session = Session.objects.create(identifiant_hakili="HAK-TEST-GEN")


class TestProblemesAVerifier(BaseGeneration):
    def test_t3_cible_les_problemes_en_remediation(self) -> None:
        en_cours = Probleme.objects.create(
            session=self.session, competence=self.idr, type_erreur=self.cpt,
            etat=EtatProbleme.EN_REMEDIATION, cout_estime=Decimal("0.5"),
        )
        Probleme.objects.create(
            session=self.session, competence=self.dev1, type_erreur=self.cpt,
            etat=EtatProbleme.CONFIRME, cout_estime=Decimal("0.5"),
        )

        cibles = problemes_a_verifier(self.session, TypeEvaluation.T3)

        self.assertEqual([p.pk for p in cibles], [en_cours.pk])

    def test_t4_et_t5_ciblent_les_problemes_resolus(self) -> None:
        resolu = Probleme.objects.create(
            session=self.session, competence=self.idr, type_erreur=self.cpt,
            etat=EtatProbleme.RESOLU, cout_estime=Decimal("0.5"),
        )
        Probleme.objects.create(
            session=self.session, competence=self.dev1, type_erreur=self.cpt,
            etat=EtatProbleme.EN_REMEDIATION, cout_estime=Decimal("0.5"),
        )

        self.assertEqual(
            [p.pk for p in problemes_a_verifier(self.session, TypeEvaluation.T4)],
            [resolu.pk],
        )
        self.assertEqual(
            [p.pk for p in problemes_a_verifier(self.session, TypeEvaluation.T5)],
            [resolu.pk],
        )

    def test_rien_a_cibler_rend_une_liste_vide(self) -> None:
        self.assertEqual(problemes_a_verifier(self.session, TypeEvaluation.T3), [])

    def test_type_sans_sujet_de_verification_leve(self) -> None:
        with self.assertRaises(ValueError):
            problemes_a_verifier(self.session, TypeEvaluation.T1)


class TestGenererSujetVerification(BaseGeneration):
    def test_rien_a_verifier_rend_none_sans_appeler_le_client(self) -> None:
        from suivi.generation import generer_sujet_verification

        with patch("suivi.generation._client") as client:
            resultat = generer_sujet_verification(self.session, TypeEvaluation.T3)

        client.assert_not_called()
        self.assertIsNone(resultat)

    def test_client_indisponible_rend_none(self) -> None:
        from suivi.generation import generer_sujet_verification

        Probleme.objects.create(
            session=self.session, competence=self.idr, type_erreur=self.cpt,
            etat=EtatProbleme.EN_REMEDIATION, cout_estime=Decimal("0.5"),
        )

        with patch("suivi.generation._client", return_value=None):
            resultat = generer_sujet_verification(self.session, TypeEvaluation.T3)

        self.assertIsNone(resultat)

    def test_sujet_valide_est_retourne(self) -> None:
        from src.models.domain import Exercise, VerificationSubject
        from suivi.generation import generer_sujet_verification

        Probleme.objects.create(
            session=self.session, competence=self.idr, type_erreur=self.cpt,
            etat=EtatProbleme.EN_REMEDIATION, cout_estime=Decimal("0.5"),
        )

        sujet = VerificationSubject(
            copy_id="verif-1-t3",
            type_evaluation="T3",
            exercises=[
                Exercise(number=1, topic="Identites remarquables × Erreur conceptuelle",
                         question="Developpe (x+2)^2", hint=None),
                Exercise(number=2, topic="Identites remarquables × Erreur conceptuelle",
                         question="Developpe (3a-1)^2", hint=None),
            ],
        )
        client_factice = type("ClientFactice", (), {
            "generate_verification_subject": lambda self, request: type(
                "Reponse", (), {"success": True, "data": sujet, "error": None}
            )(),
        })()

        with patch("suivi.generation._client", return_value=client_factice):
            resultat = generer_sujet_verification(self.session, TypeEvaluation.T3)

        self.assertIsNotNone(resultat)
        self.assertEqual(resultat.type_evaluation, "T3")
        self.assertEqual(len(resultat.exercises), 2)
