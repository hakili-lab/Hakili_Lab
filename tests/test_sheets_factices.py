"""Le jeu d'identités factices ne doit servir qu'en développement.

Ces tests portent sur la seule propriété qui compte vraiment : **il est
impossible qu'un enseignant voie des élèves inventés en croyant consulter sa
classe.** Le reste (le contenu du jeu) peut changer librement.

Le second groupe vérifie que le branchement se fait bien *au ras du réseau* :
les lignes factices portent les en-têtes réels du Sheet et traversent toute la
chaîne de traitement, sinon elles ne prouveraient rien des écrans qu'elles
remplissent.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.integrations import sheets_factices


class TestVerrouSurDebug:
    """Hors DEBUG, le réglage doit être inopérant — c'est tout l'enjeu."""

    def test_ignore_hors_debug(self, caplog: pytest.LogCaptureFixture) -> None:
        with patch.dict(
            os.environ, {"HAKILI_SHEETS_FACTICES": "true", "DEBUG": "false"}, clear=False
        ):
            assert sheets_factices.actif() is False, (
                "HAKILI_SHEETS_FACTICES ne doit JAMAIS être actif hors DEBUG : "
                "l'application servirait des élèves inventés sans que l'écran le dise."
            )

    def test_l_oubli_est_journalise(self, caplog: pytest.LogCaptureFixture) -> None:
        """Silencieusement ignoré, le réglage laisserait croire à une panne réseau."""
        with patch.dict(
            os.environ, {"HAKILI_SHEETS_FACTICES": "true", "DEBUG": "false"}, clear=False
        ):
            with caplog.at_level("ERROR"):
                sheets_factices.actif()
        assert "IGNORÉ" in caplog.text

    def test_ignore_sans_demande_explicite(self) -> None:
        """DEBUG seul ne suffit pas : il faut l'avoir demandé."""
        with patch.dict(os.environ, {"DEBUG": "true"}, clear=False):
            os.environ.pop("HAKILI_SHEETS_FACTICES", None)
            assert sheets_factices.actif() is False

    def test_actif_en_debug_sur_demande(self) -> None:
        with patch.dict(
            os.environ, {"HAKILI_SHEETS_FACTICES": "true", "DEBUG": "true"}, clear=False
        ):
            assert sheets_factices.actif() is True


class TestLignesBrutes:
    def test_sheet_inconnu_rend_none_pas_une_liste_vide(self) -> None:
        """`None` = « je ne couvre pas ce Sheet », `[]` = « ce Sheet est vide ».

        Les confondre afficherait « aucun élève » à la place d'une panne de
        configuration — le pire des deux messages, parce qu'il n'appelle pas à
        vérifier quoi que ce soit.
        """
        assert sheets_factices.lignes_brutes("un-id-quelconque", "autre chose") is None

    def test_en_tetes_reels_du_sheet(self) -> None:
        """Les clés sont les en-têtes du Sheet, pas les noms logiques.

        C'est ce qui fait passer les lignes par `_resoudre_colonnes` comme les
        vraies. Avec des noms logiques, la résolution des colonnes ne serait
        jamais exercée en développement et une régression y passerait inaperçue.
        """
        from src.integrations.google_sheets import _COLONNES_ELEVES

        lignes = sheets_factices.lignes_brutes("", "élèves")
        assert lignes
        for attendu in _COLONNES_ELEVES.values():
            assert attendu in lignes[0], f"en-tête {attendu!r} absent du jeu factice"

    def test_les_lignes_rendues_sont_des_copies(self) -> None:
        """Un appelant qui modifie sa ligne ne doit pas altérer le jeu partagé."""
        premier = sheets_factices.lignes_brutes("", "élèves")[0]
        premier["Nom"] = "MODIFIÉ"
        assert sheets_factices.lignes_brutes("", "élèves")[0]["Nom"] != "MODIFIÉ"


class TestTraverseeDeLaChaine:
    """Le jeu doit produire de vrais élèves, en passant par le vrai code."""

    @pytest.fixture(autouse=True)
    def _activer(self):
        from src.integrations import google_sheets

        google_sheets.clear_cache()
        with patch.dict(
            os.environ, {"HAKILI_SHEETS_FACTICES": "true", "DEBUG": "true"}, clear=False
        ):
            yield
        google_sheets.clear_cache()

    def test_get_eleves_sans_identifiant_de_sheet(self) -> None:
        """Le cas qui motive tout le module : `.env` sans identifiant de Sheet."""
        from src.integrations.google_sheets import get_eleves

        eleves = get_eleves()
        assert len(eleves) >= 10
        assert all(e["identifiant_hakili"] for e in eleves)

    def test_les_freres_et_soeurs_restent_distincts(self) -> None:
        """Même contact parents, prénoms différents → deux identifiants.

        Le jeu contient exprès deux SAWADOGO au même numéro : sans eux, la règle
        de `build_identifiant_hakili` ne serait pas exercée par les données de
        développement.
        """
        from src.integrations.google_sheets import get_eleves

        sawadogo = [e for e in get_eleves() if e["nom"] == "SAWADOGO"]
        assert len(sawadogo) == 2
        assert len({e["identifiant_hakili"] for e in sawadogo}) == 2

    def test_le_personnel_est_regroupe_par_personne(self) -> None:
        """KONE a deux affectations dans le Sheet, une seule ligne à l'écran."""
        from src.integrations.google_sheets import get_personnel

        kone = [p for p in get_personnel() if p["nom"] == "KONE"]
        assert len(kone) == 1, "les affectations multiples doivent être regroupées"

    def test_les_centres_sont_derives_pas_figes(self) -> None:
        from src.integrations.google_sheets import get_centres_derives

        canoniques = {info["canonique"] for info in get_centres_derives().values()}
        assert {"Ouagadougou", "Bobo-Dioulasso", "Ouahigouya"} <= canoniques
