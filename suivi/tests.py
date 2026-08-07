"""
Tests du socle de données (module 1).

Le test central est `test_parcours_complet_t0_a_t5` : c'est le critère de fin du
module 1 tel qu'écrit dans guide-v2.md — « un élève fictif peut être suivi de T0
à T5 avec toutes ses transitions enregistrées ».

Les autres vérifient que les invariants sont tenus **par la base et le modèle**,
pas par la discipline de celui qui écrit le code appelant. C'est la différence
entre une règle et une convention.

Lancement :
    DEBUG=true DATABASE_URL="sqlite://:memory:" python manage.py test suivi referentiel
"""
from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from referentiel.models import Competence, CoutRemediation, Question, TypeErreur
from django.utils import timezone

from suivi.models import (
    EtatProbleme,
    EtatSession,
    Evaluation,
    Palier,
    Probleme,
    Session,
    Transition,
    TypeEvaluation,
)


class SocleTestCase(TestCase):
    """Jeu de données minimal, calqué sur des valeurs réelles du référentiel."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.cpt = TypeErreur.objects.create(
            code="CPT", libelle="Erreur conceptuelle", definition="…",
            signature="…", coefficient=Decimal("0.35"), remediable=True,
        )
        cls.att = TypeErreur.objects.create(
            code="ATT", libelle="Inattention", definition="…",
            signature="…", coefficient=Decimal("0.00"), remediable=False,
        )
        cls.prc = TypeErreur.objects.create(
            code="PRC", libelle="Erreur procédurale", definition="…",
            signature="…", coefficient=Decimal("0.15"), remediable=True,
        )
        cls.dev1 = Competence.objects.create(
            code="L.DEV1", domaine="Calcul litteral et algebre",
            libelle="Developpement et reduction", niveau_intro="5eme",
            volume_horaire=Decimal("4.5"),
        )
        cls.idr = Competence.objects.create(
            code="L.IDR", domaine="Calcul litteral et algebre",
            libelle="Identites remarquables : developpement", niveau_intro="4eme",
            volume_horaire=Decimal("2"),
        )
        CoutRemediation.objects.create(
            competence=cls.idr, type_erreur=cls.cpt, cout_heures=Decimal("0.5")
        )
        CoutRemediation.objects.create(
            competence=cls.dev1, type_erreur=cls.prc, cout_heures=Decimal("0.5")
        )


class TestParcoursEleve(SocleTestCase):
    def test_parcours_complet_t0_a_t5(self) -> None:
        """Critère de fin du module 1 : un élève suivi de T0 à T5, toutes
        transitions enregistrées."""
        session = Session.objects.create(identifiant_hakili="HAK-TEST-001")

        evals = {
            t: Evaluation.objects.create(session=session, type=t)
            for t in (
                TypeEvaluation.T0, TypeEvaluation.T1,
                TypeEvaluation.T3, TypeEvaluation.T4, TypeEvaluation.T5,
            )
        }

        # T0 — le diagnostic émet deux hypothèses et une étourderie suspectée.
        confirme_ensuite = Probleme.objects.create(
            session=session, competence=self.idr, type_erreur=self.cpt,
            cout_estime=Decimal("0.5"),
        )
        resiste_ensuite = Probleme.objects.create(
            session=session, competence=self.dev1, type_erreur=self.prc,
            cout_estime=Decimal("0.5"),
        )
        etourderie = Probleme.objects.create(
            session=session, competence=self.dev1, type_erreur=self.att,
        )
        self.assertEqual(
            Probleme.objects.filter(etat=EtatProbleme.HYPOTHESE).count(), 3
        )

        # T1 — confirmation : deux confirmés, l'étourderie écartée.
        confirme_ensuite.changer_etat(EtatProbleme.CONFIRME, evaluation=evals["T1"])
        resiste_ensuite.changer_etat(EtatProbleme.CONFIRME, evaluation=evals["T1"])
        etourderie.changer_etat(EtatProbleme.ECARTE, evaluation=evals["T1"])

        # Le palier découle du coût des problèmes confirmés (module 6).
        self.assertEqual(session.cout_total_confirme, Decimal("1.00"))

        # Remédiation.
        confirme_ensuite.changer_etat(EtatProbleme.EN_REMEDIATION)
        resiste_ensuite.changer_etat(EtatProbleme.EN_REMEDIATION)

        # T3 — sortie : l'un résolu, l'autre non.
        confirme_ensuite.changer_etat(EtatProbleme.RESOLU, evaluation=evals["T3"])
        resiste_ensuite.changer_etat(EtatProbleme.NON_RESOLU, evaluation=evals["T3"])

        # T4 — rétention : régression, donc reprise de remédiation.
        confirme_ensuite.changer_etat(EtatProbleme.REGRESSE, evaluation=evals["T4"])
        confirme_ensuite.changer_etat(EtatProbleme.EN_REMEDIATION)
        confirme_ensuite.changer_etat(EtatProbleme.RESOLU)

        # T5 — acquis durablement.
        confirme_ensuite.changer_etat(EtatProbleme.CLOS, evaluation=evals["T5"])

        confirme_ensuite.refresh_from_db()
        resiste_ensuite.refresh_from_db()
        etourderie.refresh_from_db()
        self.assertEqual(confirme_ensuite.etat, EtatProbleme.CLOS)
        self.assertEqual(resiste_ensuite.etat, EtatProbleme.NON_RESOLU)
        self.assertEqual(etourderie.etat, EtatProbleme.ECARTE)

        # Chaque changement a laissé sa trace : 7 + 3 + 1 transitions.
        # (hypothèse→confirmé→remédiation→résolu→régressé→remédiation→résolu→clos)
        self.assertEqual(confirme_ensuite.transitions.count(), 7)
        self.assertEqual(resiste_ensuite.transitions.count(), 3)
        self.assertEqual(etourderie.transitions.count(), 1)

        # L'historique se relit dans l'ordre, sans trou : l'état d'arrivée de
        # chaque transition est l'état de départ de la suivante.
        for probleme in (confirme_ensuite, resiste_ensuite, etourderie):
            etats = list(
                probleme.transitions.order_by("date", "pk").values_list(
                    "etat_avant", "etat_apres"
                )
            )
            self.assertEqual(etats[0][0], EtatProbleme.HYPOTHESE)
            for (_, apres), (avant_suivant, _) in zip(etats, etats[1:]):
                self.assertEqual(apres, avant_suivant)
            self.assertEqual(etats[-1][1], probleme.etat)

    def test_indicateur_taux_de_confirmation_calculable(self) -> None:
        """Indicateur 4 du module 9 : problèmes confirmés / hypothèses émises.
        Il mesure la qualité du diagnostic, pas l'élève — plage saine 60-80 %."""
        session = Session.objects.create(identifiant_hakili="HAK-TEST-002")
        t1 = Evaluation.objects.create(session=session, type=TypeEvaluation.T1)

        problemes = [
            Probleme.objects.create(
                session=session, competence=c, type_erreur=t, cout_estime=Decimal("0.5")
            )
            for c, t in ((self.idr, self.cpt), (self.dev1, self.prc), (self.dev1, self.att))
        ]
        problemes[0].changer_etat(EtatProbleme.CONFIRME, evaluation=t1)
        problemes[1].changer_etat(EtatProbleme.CONFIRME, evaluation=t1)
        problemes[2].changer_etat(EtatProbleme.ECARTE, evaluation=t1)

        hypotheses = Transition.objects.filter(
            probleme__session=session, etat_avant=EtatProbleme.HYPOTHESE
        ).count()
        confirmes = Transition.objects.filter(
            probleme__session=session, etat_apres=EtatProbleme.CONFIRME
        ).count()
        self.assertEqual(hypotheses, 3)
        self.assertEqual(confirmes, 2)
        self.assertAlmostEqual(confirmes / hypotheses, 2 / 3, places=4)



def _confirmer(session, nombre: int, cout: str, type_erreur) -> None:
    """Crée `nombre` problèmes confirmés, sur autant de compétences distinctes.

    Une compétence par problème : la contrainte d'unicité interdit deux fois le
    même couple (compétence, type d'erreur) dans une session — sans quoi il
    compterait double dans tous les indicateurs.
    """
    from decimal import Decimal as D

    for i in range(nombre):
        competence = Competence.objects.create(
            code=f"X.{session.pk}.{i}", domaine="Activites numeriques",
            libelle=f"Compétence de test {i}", niveau_intro="4eme",
            volume_horaire=D("4"),
        )
        Probleme.objects.create(
            session=session, competence=competence, type_erreur=type_erreur,
            cout_estime=D(cout),
        ).changer_etat(EtatProbleme.CONFIRME)


class TestInscriptionAuProgramme(SocleTestCase):
    """L'inscription est la décision humaine du cycle — et le moment où le palier
    cesse d'être une estimation pour devenir un engagement."""

    def _session_avec_confirmes(self, nb: int, cout: str = "0.5") -> Session:
        session = Session.objects.create(identifiant_hakili="HAK-INSC")
        _confirmer(session, nb, cout, self.cpt)
        return session

    def test_inscription_bascule_les_problemes_en_remediation(self) -> None:
        session = self._session_avec_confirmes(2)
        session.inscrire()

        session.refresh_from_db()
        self.assertTrue(session.inscrite)
        self.assertIsNotNone(session.date_inscription)
        self.assertEqual(
            session.problemes.filter(etat=EtatProbleme.EN_REMEDIATION).count(), 2
        )

    def test_chaque_bascule_laisse_une_transition(self) -> None:
        session = self._session_avec_confirmes(2)
        session.inscrire()
        for probleme in session.problemes.all():
            derniere = probleme.transitions.order_by("-date", "-pk").first()
            self.assertEqual(derniere.etat_apres, EtatProbleme.EN_REMEDIATION)
            self.assertIn("Inscription au programme", derniere.commentaire)

    def test_inscription_sans_probleme_confirme_refusee(self) -> None:
        """Il n'y a rien à remédier : inscrire créerait une facturation sans objet."""
        session = Session.objects.create(identifiant_hakili="HAK-VIDE")
        with self.assertRaises(ValidationError) as ctx:
            session.inscrire()
        self.assertIn("rien à remédier", str(ctx.exception))

    def test_double_inscription_refusee(self) -> None:
        session = self._session_avec_confirmes(2)
        session.inscrire()
        with self.assertRaises(ValidationError):
            session.inscrire()

    def test_palier_c_refuse_sans_decision_explicite(self) -> None:
        """Proposer un parcours court à un élève qui cumule plus de 20 h garantit
        un échec — et un échec visible coûte plus cher qu'un refus argumenté."""
        session = self._session_avec_confirmes(12, cout="2")  # 24 h
        session.etablir_le_plan()
        self.assertEqual(session.palier, Palier.C)

        with self.assertRaises(ValidationError) as ctx:
            session.inscrire()
        self.assertIn("Palier C", str(ctx.exception))
        self.assertIn("accompagnement régulier", str(ctx.exception))

    def test_palier_c_forcable_avec_motif(self) -> None:
        session = self._session_avec_confirmes(12, cout="2")
        session.etablir_le_plan()
        session.inscrire(forcer=True, motif="Demande écrite de la famille")

        session.refresh_from_db()
        self.assertTrue(session.inscrite)
        derniere = session.problemes.first().transitions.order_by("-pk").first()
        self.assertIn("Demande écrite de la famille", derniere.commentaire)

    def test_passage_outre_exige_un_motif(self) -> None:
        """Sans motif, la décision ne serait tracée nulle part."""
        session = self._session_avec_confirmes(12, cout="2")
        session.etablir_le_plan()
        with self.assertRaises(ValidationError) as ctx:
            session.inscrire(forcer=True, motif="   ")
        self.assertIn("motif", str(ctx.exception))


class TestOrientationApresT1(SocleTestCase):
    """Trois sorties possibles, qui ne veulent pas dire la même chose."""

    def test_aucune_lacune_confirmee_est_un_bon_resultat(self) -> None:
        """« Un outil qui n'oriente pas systématiquement vers de la remédiation
        payante est un outil crédible. » À ne pas confondre avec un abandon."""
        session = Session.objects.create(identifiant_hakili="HAK-RAS")
        Probleme.objects.create(
            session=session, competence=self.idr, type_erreur=self.att
        ).changer_etat(EtatProbleme.ECARTE)

        session.etablir_le_plan()
        session.refresh_from_db()
        self.assertEqual(session.etat, EtatSession.SANS_SUITE)
        self.assertNotEqual(session.etat, EtatSession.ABANDONNEE)
        self.assertTrue(session.terminee)

    def test_palier_c_oriente_hors_dispositif(self) -> None:
        session = Session.objects.create(identifiant_hakili="HAK-C")
        _confirmer(session, 12, "2", self.cpt)

        session.etablir_le_plan()
        session.refresh_from_db()
        self.assertEqual(session.etat, EtatSession.HORS_DISPOSITIF)
        self.assertEqual(session.palier, Palier.C)

    def test_palier_b_attend_l_inscription(self) -> None:
        session = Session.objects.create(identifiant_hakili="HAK-B")
        _confirmer(session, 6, "2", self.cpt)

        session.etablir_le_plan()
        session.refresh_from_db()
        self.assertEqual(session.etat, EtatSession.ATTENTE_INSCRIPTION)
        self.assertEqual(session.palier, Palier.B)
        self.assertIsNone(session.date_inscription)

    def test_palier_a_attend_aussi_l_inscription(self) -> None:
        session = Session.objects.create(identifiant_hakili="HAK-A")
        Probleme.objects.create(
            session=session, competence=self.idr, type_erreur=self.cpt,
            cout_estime=Decimal("0.5"),
        ).changer_etat(EtatProbleme.CONFIRME)

        session.etablir_le_plan()
        session.refresh_from_db()
        self.assertEqual(session.etat, EtatSession.ATTENTE_INSCRIPTION)
        self.assertEqual(session.palier, Palier.A)


class TestClotureSession(SocleTestCase):
    def test_cloture_apres_le_cycle(self) -> None:
        session = Session.objects.create(identifiant_hakili="HAK-FIN")
        session.cloturer()
        session.refresh_from_db()
        self.assertEqual(session.etat, EtatSession.CLOSE)
        self.assertIsNotNone(session.date_cloture)

    def test_double_cloture_refusee(self) -> None:
        session = Session.objects.create(identifiant_hakili="HAK-FIN2")
        session.cloturer()
        with self.assertRaises(ValidationError):
            session.cloturer()

    def test_session_en_cours_na_pas_de_date_de_cloture(self) -> None:
        """Une date de clôture sur une session en cours fausserait les durées."""
        session = Session.objects.create(identifiant_hakili="HAK-INCOH")
        session.date_cloture = timezone.localdate()
        with self.assertRaises(IntegrityError), transaction.atomic():
            session.save()

    def test_remediation_exige_une_date_d_inscription(self) -> None:
        session = Session.objects.create(identifiant_hakili="HAK-INCOH2")
        session.etat = EtatSession.REMEDIATION
        with self.assertRaises(IntegrityError), transaction.atomic():
            session.save()


class TestInvariantsProbleme(SocleTestCase):
    def setUp(self) -> None:
        self.session = Session.objects.create(identifiant_hakili="HAK-TEST-INV")

    def _probleme(self, type_erreur=None) -> Probleme:
        return Probleme.objects.create(
            session=self.session,
            competence=self.idr,
            type_erreur=type_erreur or self.cpt,
            cout_estime=Decimal("0.5"),
        )

    def test_transition_interdite_refusee(self) -> None:
        """Une hypothèse ne peut pas passer directement en résolu : elle n'a même
        pas encore été confirmée."""
        probleme = self._probleme()
        with self.assertRaises(ValidationError) as ctx:
            probleme.changer_etat(EtatProbleme.RESOLU)
        self.assertIn("non permise", str(ctx.exception))
        probleme.refresh_from_db()
        self.assertEqual(probleme.etat, EtatProbleme.HYPOTHESE)
        self.assertEqual(probleme.transitions.count(), 0)

    def test_etat_terminal_bloque(self) -> None:
        probleme = self._probleme()
        probleme.changer_etat(EtatProbleme.ECARTE)
        with self.assertRaises(ValidationError):
            probleme.changer_etat(EtatProbleme.CONFIRME)

    def test_att_ne_peut_pas_etre_confirme(self) -> None:
        """`ATT` existe pour être écarté. Un problème d'inattention « confirmé »
        n'a pas de sens : le test de confirmation sert précisément à distinguer
        l'élève qui ne sait pas de celui qui a recopié de travers. Lui prescrire de
        la remédiation serait une erreur de diagnostic et une dépense inutile pour
        la famille."""
        probleme = Probleme.objects.create(
            session=self.session, competence=self.idr, type_erreur=self.att
        )
        with self.assertRaises(ValidationError) as ctx:
            probleme.changer_etat(EtatProbleme.CONFIRME)
        self.assertIn("ATT", str(ctx.exception))

        probleme.refresh_from_db()
        self.assertEqual(probleme.etat, EtatProbleme.HYPOTHESE)
        self.assertEqual(probleme.transitions.count(), 0)

    def test_att_peut_etre_ecarte(self) -> None:
        """C'est le seul chemin de sortie prévu pour une inattention."""
        probleme = Probleme.objects.create(
            session=self.session, competence=self.idr, type_erreur=self.att
        )
        probleme.changer_etat(EtatProbleme.ECARTE)
        probleme.refresh_from_db()
        self.assertEqual(probleme.etat, EtatProbleme.ECARTE)
        self.assertEqual(probleme.transitions.count(), 1)

    def test_changer_etat_est_atomique(self) -> None:
        """Si la transition ne peut pas s'écrire, l'état ne doit pas changer :
        un état modifié sans transition rendrait les indicateurs faux en silence."""
        probleme = self._probleme()
        avant = probleme.etat
        with self.assertRaises(ValidationError):
            probleme.changer_etat(avant)  # même état → refusé
        probleme.refresh_from_db()
        self.assertEqual(probleme.etat, avant)

    def test_probleme_unique_par_session(self) -> None:
        """Deux lignes pour le même couple compteraient double partout."""
        self._probleme()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._probleme()

    def test_meme_couple_permis_dans_deux_sessions(self) -> None:
        autre = Session.objects.create(identifiant_hakili="HAK-TEST-AUTRE")
        self._probleme()
        Probleme.objects.create(
            session=autre, competence=self.idr, type_erreur=self.cpt
        )
        self.assertEqual(Probleme.objects.count(), 2)


class TestTransitionImmuable(SocleTestCase):
    def test_transition_non_modifiable(self) -> None:
        session = Session.objects.create(identifiant_hakili="HAK-TEST-IMM")
        probleme = Probleme.objects.create(
            session=session, competence=self.idr, type_erreur=self.cpt
        )
        transition = probleme.changer_etat(EtatProbleme.CONFIRME)

        transition.commentaire = "réécriture de l'histoire"
        with self.assertRaises(ValidationError) as ctx:
            transition.save()
        self.assertIn("ne se modifie pas", str(ctx.exception))

    def test_transition_doit_changer_l_etat(self) -> None:
        session = Session.objects.create(identifiant_hakili="HAK-TEST-IMM2")
        probleme = Probleme.objects.create(
            session=session, competence=self.idr, type_erreur=self.cpt
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Transition.objects.create(
                probleme=probleme,
                etat_avant=EtatProbleme.HYPOTHESE,
                etat_apres=EtatProbleme.HYPOTHESE,
            )


class TestInvariantsEvaluation(SocleTestCase):
    def test_un_type_peut_se_repeter(self) -> None:
        """Tant que des lacunes persistent, l'enseignant relance un test de
        vérification. Le rang les distingue."""
        session = Session.objects.create(identifiant_hakili="HAK-TEST-EVAL")
        premier = Evaluation.objects.create(session=session, type=TypeEvaluation.T3)
        second = Evaluation.objects.create(session=session, type=TypeEvaluation.T3)

        self.assertEqual(premier.numero, 1)
        self.assertEqual(second.numero, 2)
        self.assertEqual(session.evaluations.filter(type=TypeEvaluation.T3).count(), 2)

    def test_le_rang_est_attribue_sans_intervention(self) -> None:
        """Un rang oublié ferait échouer l'insertion sur la contrainte d'unicité,
        avec un message incompréhensible."""
        session = Session.objects.create(identifiant_hakili="HAK-TEST-RANG")
        rangs = [
            Evaluation.objects.create(session=session, type=TypeEvaluation.T3).numero
            for _ in range(3)
        ]
        self.assertEqual(rangs, [1, 2, 3])

    def test_le_rang_est_propre_a_chaque_type(self) -> None:
        session = Session.objects.create(identifiant_hakili="HAK-TEST-RANG2")
        t1 = Evaluation.objects.create(session=session, type=TypeEvaluation.T1)
        t3 = Evaluation.objects.create(session=session, type=TypeEvaluation.T3)
        self.assertEqual((t1.numero, t3.numero), (1, 1))

    def test_deux_evaluations_ne_partagent_pas_un_rang(self) -> None:
        session = Session.objects.create(identifiant_hakili="HAK-TEST-RANG3")
        Evaluation.objects.create(session=session, type=TypeEvaluation.T3)
        with self.assertRaises(IntegrityError), transaction.atomic():
            doublon = Evaluation(session=session, type=TypeEvaluation.T3, numero=1)
            doublon._state.adding = False  # court-circuite l'attribution du rang
            doublon.save(force_insert=True)

    def test_libelle_signale_les_passages_suivants(self) -> None:
        session = Session.objects.create(identifiant_hakili="HAK-TEST-LIB")
        premier = Evaluation.objects.create(session=session, type=TypeEvaluation.T3)
        second = Evaluation.objects.create(session=session, type=TypeEvaluation.T3)
        self.assertNotIn("passage", premier.libelle)
        self.assertIn("2e passage", second.libelle)

    def test_t2_retire_du_cycle(self) -> None:
        """Le cycle réel va de la fin du volume horaire directement à la
        vérification — voir TypeEvaluation."""
        self.assertNotIn("T2", [t.value for t in TypeEvaluation])

    def test_evaluation_sans_copie_permise(self) -> None:
        """Une évaluation peut être saisie à la main, sans scan (module 8)."""
        session = Session.objects.create(identifiant_hakili="HAK-TEST-EVAL2")
        evaluation = Evaluation.objects.create(
            session=session, type=TypeEvaluation.T1, support="saisie manuelle"
        )
        self.assertIsNone(evaluation.copie)


class TestCoutRemediation(SocleTestCase):
    def test_att_sans_ligne_de_cout_est_normal(self) -> None:
        """444 lignes = 74 compétences × 6 types remédiables : `ATT` n'y figure
        jamais. Le module 6 doit traiter l'absence comme un coût 0, pas comme une
        anomalie."""
        self.assertFalse(
            CoutRemediation.objects.filter(type_erreur=self.att).exists()
        )
        session = Session.objects.create(identifiant_hakili="HAK-TEST-COUT")
        Probleme.objects.create(
            session=session, competence=self.idr, type_erreur=self.att
        )
        self.assertEqual(session.cout_total_confirme, Decimal("0"))

    def test_cout_total_ne_compte_que_les_confirmes(self) -> None:
        session = Session.objects.create(identifiant_hakili="HAK-TEST-COUT2")
        hypothese = Probleme.objects.create(
            session=session, competence=self.idr, type_erreur=self.cpt,
            cout_estime=Decimal("0.5"),
        )
        confirme = Probleme.objects.create(
            session=session, competence=self.dev1, type_erreur=self.prc,
            cout_estime=Decimal("0.5"),
        )
        confirme.changer_etat(EtatProbleme.CONFIRME)

        self.assertEqual(session.cout_total_confirme, Decimal("0.50"))
        self.assertEqual(hypothese.etat, EtatProbleme.HYPOTHESE)
