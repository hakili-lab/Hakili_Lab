"""Tests du dépôt de copies — la couture entre le pipeline et la base (D-CEO-40).

Ce que ces tests protègent, dans l'ordre du risque :

1. **Les quatre opérations sont rejouables.** Le pipeline enveloppe chaque
   écriture dans un retry, parce qu'une base serverless refuse parfois la
   première connexion après une inactivité. Si une opération n'est pas
   rejouable, ce retry ne rattrape rien — il aggrave.
2. **Un document remplace celui de même type.** Sinon une copie recorrigée
   accumule les rapports et en sert un ancien, sans que rien ne le signale.
3. **Le pipeline tourne sans base.** Le dépôt neutre ne doit jamais lever.
"""
from __future__ import annotations

from django.test import TestCase

from correction_web.depot import DepotDjango
from src.pipeline.depot import depot, installer_depot
from suivi.models import Copie, Document


class TestDepotDjango(TestCase):
    def setUp(self) -> None:
        self.depot = DepotDjango()
        self.depot.creer_copie(
            copy_id="copie-1",
            identifiant_hakili="HAK-2026-0001",
            classe="3e",
            annee_scolaire="2026",
        )

    def test_creer_copie_est_rejouable(self) -> None:
        """Le retry du pipeline la rappelle telle quelle après un échec réseau."""
        self.depot.creer_copie(
            copy_id="copie-1",
            identifiant_hakili="HAK-2026-0001",
            classe="3e",
            annee_scolaire="2026",
        )
        self.assertEqual(Copie.objects.filter(copy_id="copie-1").count(), 1)

    def test_un_document_par_type(self) -> None:
        for contenu in (b"premier rapport", b"rapport recorrige"):
            self.depot.ajouter_document(
                copy_id="copie-1", type_document="rapport", contenu=contenu
            )
        documents = Document.objects.filter(copie_id="copie-1", type="rapport")
        self.assertEqual(documents.count(), 1)
        self.assertEqual(bytes(documents.get().fichier), b"rapport recorrige")

    def test_les_types_ne_se_chassent_pas_entre_eux(self) -> None:
        for type_doc in ("scan", "rapport", "remediation"):
            self.depot.ajouter_document(
                copy_id="copie-1", type_document=type_doc, contenu=b"x"
            )
        self.assertEqual(Document.objects.filter(copie_id="copie-1").count(), 3)

    def test_maj_notes_et_classe(self) -> None:
        self.depot.maj_notes(copy_id="copie-1", notes_finales=14.5)
        self.depot.maj_classe(copy_id="copie-1", classe="3e A")
        copie = Copie.objects.get(copy_id="copie-1")
        self.assertEqual(copie.notes_finales, 14.5)
        self.assertEqual(copie.classe, "3e A")

    def test_maj_sur_copie_absente_ne_leve_pas(self) -> None:
        """Le point 1 peut avoir échoué : les points 4 et 5 ne doivent pas
        transformer une écriture manquée en plantage du pipeline."""
        self.depot.maj_notes(copy_id="jamais-creee", notes_finales=12.0)
        self.depot.maj_classe(copy_id="jamais-creee", classe="4e")

    def test_le_depot_django_est_installe_au_demarrage(self) -> None:
        """`CorrectionWebConfig.ready()` l'installe — sans quoi le pipeline
        écrirait dans le vide sans que rien ne le dise."""
        self.assertIsInstance(depot(), DepotDjango)


class TestDepotNeutre(TestCase):
    """Sans base configurée, la correction doit se dérouler quand même."""

    def test_aucune_operation_ne_leve(self) -> None:
        from src.pipeline.depot import _DepotNeutre

        courant = depot()
        self.addCleanup(installer_depot, courant)
        installer_depot(_DepotNeutre())

        neutre = depot()
        neutre.creer_copie(
            copy_id="c", identifiant_hakili="h", classe="3e", annee_scolaire="2026"
        )
        neutre.ajouter_document(copy_id="c", type_document="scan", contenu=b"x")
        neutre.maj_notes(copy_id="c", notes_finales=10.0)
        neutre.maj_classe(copy_id="c", classe="3e")
        self.assertEqual(Copie.objects.count(), 0)
