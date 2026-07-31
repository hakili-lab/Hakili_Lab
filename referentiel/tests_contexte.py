"""
Tests de l'ancrage du diagnostic sur le référentiel.

Ce que ces tests protègent : le diagnostic des 7 nouveaux tests tournait avec
**zéro** contexte programme, parce que l'ancrage passait par un champ `chunk_ids`
que les barèmes générés depuis le classeur n'ont pas. Le défaut était invisible —
le pipeline n'échouait pas, il produisait simplement un diagnostic générique, ce
que D-CEO-12 désigne précisément comme inutilisable.
"""
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from referentiel.contexte import contexte_diagnostic, lacunes_competences
from referentiel.models import (
    Competence,
    Prerequis,
    Question,
    SignatureErreur,
    TypeErreur,
)


class BaseContexte(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.cpt = TypeErreur.objects.create(
            code="CPT", libelle="Erreur conceptuelle", definition="…",
            signature="…", coefficient=Decimal("0.35"), remediable=True,
        )
        cls.prc = TypeErreur.objects.create(
            code="PRC", libelle="Erreur procédurale", definition="…",
            signature="…", coefficient=Decimal("0.15"), remediable=True,
        )

        # Chaîne réelle : L.IDR ← L.DEV1 ← N.RELOP
        cls.relop = Competence.objects.create(
            code="N.RELOP", domaine="Activites numeriques",
            libelle="Operations sur les relatifs", niveau_intro="5eme",
        )
        cls.dev1 = Competence.objects.create(
            code="L.DEV1", domaine="Calcul litteral et algebre",
            libelle="Developpement et reduction", niveau_intro="5eme",
        )
        cls.idr = Competence.objects.create(
            code="L.IDR", domaine="Calcul litteral et algebre",
            libelle="Identites remarquables : developpement",
            description="Developper (a+b)^2, (a-b)^2, (a+b)(a-b).",
            niveau_intro="4eme", chapitre_intro="4e ch15",
        )
        Prerequis.objects.create(competence=cls.idr, prerequis=cls.dev1)
        Prerequis.objects.create(competence=cls.dev1, prerequis=cls.relop)

        cls.question = Question.objects.create(
            code_question="L5", niveau_test="3eme", partie="A", format="qcm",
            bareme=Decimal("0.333333"), bareme_classeur=Decimal("1"),
            competence=cls.idr, objet="Developper (2x - 3)^2",
        )
        SignatureErreur.objects.create(
            question=cls.question, competence=cls.idr, type_erreur=cls.cpt,
            production_eleve="Ecrit 4x^2 + 9",
            interpretation="Le carre d'une somme est traite comme la somme des carres.",
        )
        SignatureErreur.objects.create(
            question=cls.question, competence=cls.idr, type_erreur=cls.prc,
            production_eleve="Ecrit 4x^2 - 6x + 9",
            interpretation="Le double produit est calcule sans le facteur 2.",
        )


class TestContexteDiagnostic(BaseContexte):
    def test_le_contexte_n_est_plus_vide(self) -> None:
        """Le défaut d'origine : 0 caractère pour les tests du référentiel."""
        contexte = contexte_diagnostic("3eme", ["L5"])
        self.assertGreater(len(contexte), 200)

    def test_contient_la_competence_et_son_code(self) -> None:
        contexte = contexte_diagnostic("3eme", ["L5"])
        self.assertIn("L.IDR", contexte)
        self.assertIn("Identites remarquables", contexte)

    def test_contient_la_chaine_de_prerequis(self) -> None:
        """« Remonter d'un échec vers la lacune ancienne qui l'explique, au lieu
        de traiter le symptôme » — c'est ce que le protocole demande."""
        contexte = contexte_diagnostic("3eme", ["L5"])
        self.assertIn("L.DEV1", contexte)   # prérequis direct
        self.assertIn("N.RELOP", contexte)  # prérequis du prérequis

    def test_contient_les_signatures_de_la_question(self) -> None:
        """C'est ce qui rend ce contexte meilleur que l'ancien : les signatures
        sont propres à la question, le modèle reconnaît au lieu de deviner."""
        contexte = contexte_diagnostic("3eme", ["L5"])
        self.assertIn("4x^2 + 9", contexte)
        self.assertIn("somme des carres", contexte)

    def test_demande_de_ne_pas_inventer_de_code(self) -> None:
        contexte = contexte_diagnostic("3eme", ["L5"])
        self.assertIn("jamais en inventer", contexte)

    def test_vide_sans_question_echouee(self) -> None:
        self.assertEqual(contexte_diagnostic("3eme", []), "")

    def test_vide_pour_un_niveau_inconnu(self) -> None:
        """Mode libre ou ancien test : pas d'ancrage, mais pas d'erreur non plus."""
        self.assertEqual(contexte_diagnostic("inexistant", ["L5"]), "")

    def test_question_inconnue_ignoree_sans_echouer(self) -> None:
        contexte = contexte_diagnostic("3eme", ["L5", "QUESTION_FANTOME"])
        self.assertIn("L.IDR", contexte)


class TestLacunes(BaseContexte):
    def test_une_lacune_par_competence(self) -> None:
        lacunes = lacunes_competences("3eme", ["L5"])
        self.assertEqual(len(lacunes), 1)
        self.assertEqual(lacunes[0]["chunk_id"], "L.IDR")
        self.assertEqual(lacunes[0]["classe"], "4eme")

    def test_competence_ratee_deux_fois_remontee_une_seule(self) -> None:
        """Sinon le rapport répéterait la même lacune."""
        autre = Question.objects.create(
            code_question="L9", niveau_test="3eme", partie="B", format="redige",
            bareme=Decimal("1"), bareme_classeur=Decimal("3"),
            competence=self.idr, objet="Developper E puis calculer E",
        )
        SignatureErreur.objects.create(
            question=autre, competence=self.idr, type_erreur=self.cpt,
            production_eleve="Oublie le double produit", interpretation="Même confusion.",
        )
        lacunes = lacunes_competences("3eme", ["L5", "L9"])
        self.assertEqual(len(lacunes), 1)

    def test_les_signatures_alimentent_les_erreurs_frequentes(self) -> None:
        lacunes = lacunes_competences("3eme", ["L5"])
        erreurs = lacunes[0]["erreurs_frequentes"]
        self.assertEqual(len(erreurs), 2)
        self.assertTrue(any("4x^2 + 9" in e for e in erreurs))

    def test_compatible_avec_le_modele_du_pipeline(self) -> None:
        """Les lacunes doivent pouvoir devenir des `CompetencyGap` sans adaptation."""
        from src.models.domain import CompetencyGap

        for brut in lacunes_competences("3eme", ["L5"]):
            CompetencyGap(**brut)  # lève si un champ manque ou a le mauvais type


class TestAncragePipeline(BaseContexte):
    def test_niveau_extrait_du_bareme_id(self) -> None:
        from correction_web.taches import _niveau_test

        self.assertEqual(_niveau_test("urie_3eme"), "3eme")
        self.assertEqual(_niveau_test("urie_2ndeC"), "2ndeC")
        self.assertEqual(_niveau_test("hakili_3e_v1"), "")  # ancien test
        self.assertEqual(_niveau_test(""), "")              # mode libre

    def test_ancrage_absent_hors_referentiel(self) -> None:
        """Mode libre : le pipeline doit retomber sur son chemin historique."""
        from correction_web.taches import _ancrage_referentiel

        self.assertIsNone(_ancrage_referentiel(""))

    def test_ancrage_rend_contexte_et_lacunes(self) -> None:
        from correction_web.taches import _ancrage_referentiel

        ancrer = _ancrage_referentiel("3eme")
        contexte, lacunes = ancrer(["L5"])
        self.assertIn("L.IDR", contexte)
        self.assertEqual(len(lacunes), 1)
