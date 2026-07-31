"""
Tests du tagage du corpus de référence (module 3).

Le corpus est l'étalon contre lequel le module 4 sera mesuré. Ces tests
verrouillent donc surtout des **refus** : un étalon sali par une faute de frappe
ou un code inventé ne se voit pas, et tout ce qui sera mesuré contre lui sera
faux sans que rien ne le signale.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

import yaml
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from referentiel.models import Competence, CoutRemediation, TypeErreur
from suivi.models import EtatProbleme, Evaluation, Probleme, Session


def _tagage(**surcharges) -> dict:
    base = {
        "identifiant_hakili": "HK-0042",
        "tague_par": "Urie",
        "date_tagage": date(2026, 7, 31),
        "evaluation": {
            "type": "T0",
            "date": date(2025, 11, 1),
            "support": "scan 200 DPI",
        },
        "problemes": [
            {
                "competence": "N.ENS",
                "type_erreur": "CPT",
                "etat": "hypothese",
                "justification": "confond l'ensemble des décimaux et celui des entiers",
            }
        ],
    }
    base.update(surcharges)
    return base


class _SocleCorpus:
    """Référentiel minimal + helpers, partagés par les deux classes de tests.

    Un mixin et non une classe de base : hériter d'une `TestCase` qui porte déjà
    des tests les ferait tous rejouer dans la sous-classe.
    """

    def setUp(self) -> None:
        self.competence = Competence.objects.create(
            code="N.ENS",
            domaine="Activites numeriques",
            libelle="Ensembles de nombres",
            niveau_intro="3eme",
            volume_horaire=Decimal("4"),
        )
        Competence.objects.create(
            code="N.REL",
            domaine="Activites numeriques",
            libelle="Nombres relatifs",
            niveau_intro="5eme",
            volume_horaire=Decimal("6"),
        )
        self.cpt = TypeErreur.objects.create(
            code="CPT", libelle="Conceptuelle", definition="…", signature="…",
            coefficient=Decimal("0.35"), remediable=True,
        )
        TypeErreur.objects.create(
            code="ATT", libelle="Inattention", definition="…", signature="…",
            coefficient=Decimal("0"), remediable=False,
        )
        CoutRemediation.objects.create(
            competence=self.competence, type_erreur=self.cpt, cout_heures=Decimal("1.5")
        )

    def _ecrire(self, donnees: dict) -> Path:
        chemin = Path(self.id().split(".")[-1] + ".yaml")
        chemin = Path(self._outil_tmp()) / chemin
        chemin.write_text(
            yaml.safe_dump(donnees, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        return chemin

    def _outil_tmp(self) -> str:
        import tempfile

        if not hasattr(self, "_tmp"):
            self._tmp = tempfile.mkdtemp()
        return self._tmp

    def _lancer(self, donnees: dict, *args: str) -> str:
        sortie = StringIO()
        call_command(
            "taguer_corpus", "--fichier", str(self._ecrire(donnees)), *args, stdout=sortie
        )
        return sortie.getvalue()


class TaguerCorpusTests(_SocleCorpus, TestCase):
    # ── Ce qui doit marcher ──────────────────────────────────────────────────

    def test_une_copie_taguee_entre_dans_le_corpus(self) -> None:
        self._lancer(_tagage())

        evaluation = Evaluation.objects.get()
        self.assertTrue(evaluation.corpus_reference)
        self.assertEqual(evaluation.tague_par, "Urie")
        self.assertEqual(evaluation.date_tagage, date(2026, 7, 31))

        probleme = Probleme.objects.get()
        self.assertEqual(probleme.etat, EtatProbleme.HYPOTHESE)
        self.assertEqual(probleme.evaluation_origine, evaluation)
        self.assertIn("décimaux", probleme.justification)

    def test_le_cout_est_lu_dans_le_referentiel(self) -> None:
        """Le coût n'est pas saisi à la main : il vient de CoutRemediation."""
        self._lancer(_tagage())
        self.assertEqual(Probleme.objects.get().cout_estime, Decimal("1.50"))

    def test_un_probleme_confirme_porte_sa_transition(self) -> None:
        donnees = _tagage()
        donnees["problemes"][0]["etat"] = "confirme"
        self._lancer(donnees)

        probleme = Probleme.objects.get()
        self.assertEqual(probleme.etat, EtatProbleme.CONFIRME)
        transition = probleme.transitions.get()
        self.assertEqual(transition.etat_avant, EtatProbleme.HYPOTHESE)
        self.assertEqual(transition.etat_apres, EtatProbleme.CONFIRME)
        self.assertEqual(transition.evaluation, probleme.evaluation_origine)

    def test_a_blanc_n_ecrit_rien(self) -> None:
        sortie = self._lancer(_tagage(), "--a-blanc")
        self.assertIn("rien n'a été écrit", sortie)
        self.assertFalse(Evaluation.objects.exists())
        self.assertFalse(Probleme.objects.exists())

    def test_les_hesitations_sont_remontees(self) -> None:
        """Une hésitation est un défaut possible du référentiel, pas une faute."""
        donnees = _tagage(
            hesitations=[{"sur": "question 3b", "pourquoi": "aucune signature ne colle"}]
        )
        sortie = self._lancer(donnees)
        self.assertIn("aucune signature ne colle", sortie)
        self.assertIn("défauts possibles du référentiel", sortie)

    # ── Ce qui doit être refusé ──────────────────────────────────────────────

    def test_une_competence_inventee_est_refusee(self) -> None:
        donnees = _tagage()
        donnees["problemes"][0]["competence"] = "N.INVENTEE"
        with self.assertRaisesMessage(CommandError, "absente du référentiel"):
            self._lancer(donnees)
        self.assertFalse(Probleme.objects.exists())

    def test_un_type_d_erreur_hors_liste_est_refuse(self) -> None:
        donnees = _tagage()
        donnees["problemes"][0]["type_erreur"] = "XXX"
        with self.assertRaisesMessage(CommandError, "liste fermée"):
            self._lancer(donnees)

    def test_une_justification_vide_est_refusee(self) -> None:
        """Sans justification, un désaccord avec le module 4 serait inarbitrable."""
        donnees = _tagage()
        donnees["problemes"][0]["justification"] = "   "
        with self.assertRaisesMessage(CommandError, "inarbitrable"):
            self._lancer(donnees)

    def test_att_ne_se_confirme_pas(self) -> None:
        donnees = _tagage()
        donnees["problemes"][0]["type_erreur"] = "ATT"
        donnees["problemes"][0]["etat"] = "confirme"
        with self.assertRaisesMessage(CommandError, "pour être écarté"):
            self._lancer(donnees)

    def test_un_etat_hors_tagage_est_refuse(self) -> None:
        donnees = _tagage()
        donnees["problemes"][0]["etat"] = "resolu"
        with self.assertRaisesMessage(CommandError, "hypothèse ou une confirmation"):
            self._lancer(donnees)

    def test_un_couple_en_double_est_refuse(self) -> None:
        donnees = _tagage()
        donnees["problemes"].append(dict(donnees["problemes"][0]))
        with self.assertRaisesMessage(CommandError, "deux fois"):
            self._lancer(donnees)

    def test_rien_n_est_ecrit_si_une_seule_ligne_est_fausse(self) -> None:
        """Validation complète avant écriture : un corpus à moitié écrit serait pire
        que pas de corpus du tout — il aurait l'air complet."""
        donnees = _tagage()
        donnees["problemes"].append(
            {
                "competence": "N.INCONNUE",
                "type_erreur": "CPT",
                "justification": "…",
            }
        )
        with self.assertRaises(CommandError):
            self._lancer(donnees)
        self.assertFalse(Probleme.objects.exists())
        self.assertFalse(Evaluation.objects.exists())

    def test_un_tagage_deja_enregistre_n_est_pas_ecrase_par_megarde(self) -> None:
        self._lancer(_tagage())
        with self.assertRaisesMessage(CommandError, "--remplacer"):
            self._lancer(_tagage())
        self.assertEqual(Probleme.objects.count(), 1)

    def test_remplacer_refait_le_tagage(self) -> None:
        self._lancer(_tagage())
        donnees = _tagage()
        donnees["problemes"] = [
            {
                "competence": "N.REL",
                "type_erreur": "CPT",
                "justification": "additionne deux relatifs comme des naturels",
            }
        ]
        self._lancer(donnees, "--remplacer")

        self.assertEqual(Probleme.objects.count(), 1)
        self.assertEqual(Probleme.objects.get().competence_id, "N.REL")
        self.assertEqual(Evaluation.objects.count(), 1)

    def test_remplacer_ne_touche_pas_au_suivi_reel_de_l_eleve(self) -> None:
        """Un élève du corpus peut aussi être suivi pour de vrai : refaire le
        tagage ne doit pas emporter les problèmes de son parcours."""
        self._lancer(_tagage())
        session = Session.objects.get()
        autre = Probleme.objects.create(
            session=session,
            competence_id="N.REL",
            type_erreur_id="CPT",
            cout_estime=Decimal("1"),
        )

        self._lancer(_tagage(), "--remplacer")

        self.assertTrue(Probleme.objects.filter(pk=autre.pk).exists())
        self.assertEqual(Probleme.objects.count(), 2)

    def test_un_referentiel_vide_arrete_tout(self) -> None:
        Competence.objects.all().delete()
        with self.assertRaisesMessage(CommandError, "importer_referentiel"):
            self._lancer(_tagage())

    # ── Le trou que la validation ne bouche pas : les codes valides mais faux ──

    def test_le_compte_rendu_rappelle_les_libelles(self) -> None:
        """Un code valide mais mal choisi ne se voit pas ; relu en toutes lettres,
        il a une chance de sauter aux yeux. C'est le seul filet contre l'erreur
        qui salit l'étalon sans rien casser."""
        sortie = self._lancer(_tagage())
        self.assertIn("Ensembles de nombres", sortie)
        self.assertIn("Conceptuelle", sortie)

    def test_un_code_absent_fait_proposer_les_codes_proches(self) -> None:
        donnees = _tagage()
        donnees["problemes"][0]["competence"] = "N.RELO"   # N.REL existe
        with self.assertRaises(CommandError) as ctx:
            self._lancer(donnees)
        self.assertIn("Peut-être", str(ctx.exception))
        self.assertIn("--chercher", str(ctx.exception))

    def test_chercher_donne_le_referentiel_sans_taguer(self) -> None:
        sortie = StringIO()
        call_command("taguer_corpus", "--chercher", "relatifs", stdout=sortie)
        self.assertIn("N.REL", sortie.getvalue())
        self.assertIn("Nombres relatifs", sortie.getvalue())
        self.assertFalse(Evaluation.objects.exists())

    def test_chercher_par_niveau(self) -> None:
        sortie = StringIO()
        call_command("taguer_corpus", "--chercher", "--niveau", "5eme", stdout=sortie)
        self.assertIn("N.REL", sortie.getvalue())
        self.assertNotIn("N.ENS", sortie.getvalue())   # N.ENS est en 3eme ici

    def test_sans_fichier_ni_recherche_la_commande_le_dit(self) -> None:
        with self.assertRaisesMessage(CommandError, "--fichier est obligatoire"):
            call_command("taguer_corpus")

    # ── Avertissements : suspect sans être faux ───────────────────────────────

    def test_une_competence_du_niveau_du_test_est_signalee(self) -> None:
        """Un test d'entrée en 3ème évalue ce qui précède la 3ème : une compétence
        introduite en 3ème n'a pas encore été enseignée."""
        donnees = _tagage(niveau="3eme")
        sortie = self._lancer(donnees)
        self.assertIn("pas encore été enseignée", sortie)
        self.assertEqual(Probleme.objects.count(), 1)   # signalé, pas refusé

    def test_une_competence_anterieure_ne_declenche_rien(self) -> None:
        donnees = _tagage(niveau="3eme")
        donnees["problemes"][0]["competence"] = "N.REL"   # 5eme
        sortie = self._lancer(donnees)
        self.assertNotIn("pas encore été enseignée", sortie)

    def test_une_competence_taguee_deux_fois_est_signalee(self) -> None:
        donnees = _tagage()
        donnees["problemes"].append(
            {
                "competence": "N.ENS",
                "type_erreur": "ATT",
                "justification": "une seule question ratée sur la série",
            }
        )
        sortie = self._lancer(donnees)
        self.assertIn("tagué 2 fois", sortie)
        self.assertIn("compté autant de fois", sortie)

    # ── Étanchéité avec le suivi réel ─────────────────────────────────────────

    def test_la_session_creee_est_marquee_corpus(self) -> None:
        self._lancer(_tagage())
        self.assertTrue(Session.objects.get().corpus_reference)

    def test_taguer_sur_la_session_d_un_eleve_reel_est_refuse(self) -> None:
        """Sinon les problèmes d'une copie d'archive entrent dans le palier de cet
        élève — donc dans ce que sa famille paierait."""
        Session.objects.create(identifiant_hakili="HK-0042")   # suivi réel
        with self.assertRaisesMessage(CommandError, "suivi réel"):
            self._lancer(_tagage())
        self.assertFalse(Probleme.objects.exists())

    def test_une_session_de_corpus_ne_peut_pas_etablir_de_plan(self) -> None:
        from django.core.exceptions import ValidationError

        self._lancer(_tagage())
        session = Session.objects.get()
        with self.assertRaisesMessage(ValidationError, "corpus de référence"):
            session.etablir_le_plan()

    def test_une_session_de_corpus_ne_peut_pas_inscrire(self) -> None:
        from django.core.exceptions import ValidationError

        donnees = _tagage()
        donnees["problemes"][0]["etat"] = "confirme"
        self._lancer(donnees)
        session = Session.objects.get()
        with self.assertRaisesMessage(ValidationError, "corpus de référence"):
            session.inscrire()


class EtatDuCorpusTests(_SocleCorpus, TestCase):
    """`manage.py corpus` — relire l'étalon, sans quoi il ne rassure personne."""

    def _corpus(self, *args: str) -> str:
        sortie = StringIO()
        call_command("corpus", *args, stdout=sortie)
        return sortie.getvalue()

    def test_un_corpus_vide_le_dit(self) -> None:
        self.assertIn("corpus est vide", self._corpus())

    def test_la_composition_est_rendue(self) -> None:
        self._lancer(_tagage())
        sortie = self._corpus()
        self.assertIn("HK-0042", sortie)
        self.assertIn("CPT", sortie)

    def test_le_jalon_des_cinq_copies_est_rappele(self) -> None:
        self._lancer(_tagage())
        self.assertIn("il en manque 4", self._corpus())

    def test_les_types_absents_du_corpus_sont_signales(self) -> None:
        """Un corpus sans PRQ ne permet pas de mesurer le module 4 sur PRQ."""
        self._lancer(_tagage())
        sortie = self._corpus()
        self.assertIn("Aucun problème de type", sortie)
        self.assertIn("PRQ", sortie)

    def test_la_derive_des_couts_est_detectee_et_corrigee(self) -> None:
        """Le coût est figé au tagage : si le référentiel change, il ment."""
        self._lancer(_tagage())
        CoutRemediation.objects.filter(
            competence=self.competence, type_erreur=self.cpt
        ).update(cout_heures=Decimal("2.50"))

        self.assertIn("en écart avec le référentiel", self._corpus())
        self.assertIn("À blanc", self._corpus("--recalculer", "--a-blanc"))
        self.assertEqual(Probleme.objects.get().cout_estime, Decimal("1.50"))

        self._corpus("--recalculer")
        self.assertEqual(Probleme.objects.get().cout_estime, Decimal("2.50"))
        self.assertIn("en accord avec le référentiel", self._corpus())

    def test_une_competence_taguee_deux_fois_ressort_au_bilan(self) -> None:
        donnees = _tagage()
        donnees["problemes"].append(
            {"competence": "N.ENS", "type_erreur": "ATT", "justification": "isolée"}
        )
        self._lancer(donnees)
        sortie = self._corpus()
        self.assertIn("taguées plusieurs fois", sortie)
        self.assertIn("compté 2 fois", sortie)
