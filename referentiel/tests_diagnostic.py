"""
Tests du diagnostic contraint (module 4).

Ce que ces tests protègent, dans l'ordre du risque :

1. **Aucun appel de modèle pour un QCM.** Le référentiel donne la réponse ; un
   appel de langage y introduirait une incertitude là où il n'y en a aucune, et
   la facturerait. Le test échoue si le client est seulement *touché*.
2. **Aucun code hors référentiel n'est écrit.** C'est la règle non négociable du
   protocole. Un code invalide est refusé, redemandé une fois, puis **écarté** —
   jamais réparé au jugé.
3. **Ce qui n'est pas diagnostiqué est dit.** Une question écartée en silence se
   lirait comme une réussite, et l'élève passerait pour meilleur qu'il n'est.
"""
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from referentiel.diagnostic import (
    ProductionEleve,
    ReponseEleve,
    catalogue_competences,
    codes_competence_admis,
    diagnostiquer,
    diagnostiquer_sans_ancrage,
    lettre_cochee,
    preparer,
    valider,
)
from referentiel.models import (
    Competence,
    OptionQcm,
    Prerequis,
    Question,
    SignatureErreur,
    TypeErreur,
)
from src.models.domain import (
    ClaudeResponse,
    ProblemeDetecte,
    SortieDiagnosticContraint,
    SourceProbleme,
)


class ClientFactice:
    """Client de diagnostic simulé — aucun appel réseau.

    Enregistre ce qu'il a reçu : c'est ce qui permet de vérifier qu'aucun QCM ne
    lui parvient, et que la redemande porte bien les motifs de rejet.
    """

    def __init__(self, sorties: list[SortieDiagnosticContraint]) -> None:
        self._sorties = list(sorties)
        self.appels: list[dict] = []

    def diagnose_constrained(self, **kwargs) -> ClaudeResponse:
        self.appels.append(kwargs)
        sortie = self._sorties.pop(0) if self._sorties else SortieDiagnosticContraint()
        return ClaudeResponse(
            success=True, data=sortie, confidence=1.0, raw_response="{}"
        )


class ClientMuet:
    """Le modèle ne répond pas — panne, quota, clé révoquée."""

    def diagnose_constrained(self, **kwargs) -> ClaudeResponse:
        return ClaudeResponse(
            success=False, data=None, confidence=0.0, raw_response="",
            error="429 quota dépassé",
        )


class BaseReferentiel(TestCase):
    """Un fragment de référentiel réel : L5 (QCM) et L7 (court) du test de 3ème."""

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
        cls.att = TypeErreur.objects.create(
            code="ATT", libelle="Inattention", definition="…",
            signature="…", coefficient=Decimal("0"), remediable=False,
        )

        cls.dev1 = Competence.objects.create(
            code="L.DEV1", domaine="Calcul litteral et algebre",
            libelle="Developpement et reduction", niveau_intro="5eme",
            volume_horaire=Decimal("4"),
        )
        cls.idr = Competence.objects.create(
            code="L.IDR", domaine="Calcul litteral et algebre",
            libelle="Identites remarquables : developpement",
            niveau_intro="4eme", chapitre_intro="4e ch15",
            volume_horaire=Decimal("2"),
        )
        cls.geo = Competence.objects.create(
            code="G.THA", domaine="Activites geometriques",
            libelle="Theoreme de Thales", niveau_intro="4eme",
            volume_horaire=Decimal("6"),
        )
        Prerequis.objects.create(competence=cls.idr, prerequis=cls.dev1)

        cls.qcm = Question.objects.create(
            code_question="L5", niveau_test="3eme", partie="A", format="qcm",
            bareme=Decimal("0.333333"), bareme_classeur=Decimal("1"),
            competence=cls.idr, objet="Developper (2x - 3)^2",
            reponse_attendue="d",
        )
        OptionQcm.objects.create(
            question=cls.qcm, lettre="a", texte="4x^2 + 9", correcte=False,
            type_erreur=cls.cpt, erreur="Oubli complet du double produit.",
        )
        OptionQcm.objects.create(
            question=cls.qcm, lettre="b", texte="4x^2 - 6x + 9", correcte=False,
            type_erreur=cls.prc, erreur="Double produit sans le facteur 2.",
        )
        OptionQcm.objects.create(
            question=cls.qcm, lettre="d", texte="4x^2 - 12x + 9", correcte=True,
        )

        cls.courte = Question.objects.create(
            code_question="L7", niveau_test="3eme", partie="A", format="court",
            bareme=Decimal("0.333333"), bareme_classeur=Decimal("1"),
            competence=cls.idr, objet="Factoriser x^2 - 25",
        )
        SignatureErreur.objects.create(
            question=cls.courte, competence=cls.idr, type_erreur=cls.cpt,
            production_eleve="Ecrit (x-5)^2",
            interpretation="Difference de carres confondue avec un carre parfait.",
        )

        cls.construction = Question.objects.create(
            code_question="G13", niveau_test="3eme", partie="B",
            format="construction", bareme=Decimal("1"),
            bareme_classeur=Decimal("3"), competence=cls.geo,
            objet="Construire la perpendiculaire a (AB) passant par C",
        )


# ── QCM : mécanique, sans modèle ─────────────────────────────────────────────


class TestQcm(BaseReferentiel):
    def test_aucun_appel_de_modele_pour_un_qcm(self) -> None:
        """La règle la plus explicite du module 4, et la plus facile à enfreindre."""
        client = ClientFactice([])
        resultat = diagnostiquer(
            niveau_test="3eme",
            reponses=[ReponseEleve(code_question="L5", contenu="a")],
            client=client,
            copy_id="C1",
        )
        self.assertEqual(client.appels, [], "un QCM a été soumis au modèle")
        self.assertEqual(len(resultat.problemes), 1)
        self.assertEqual(resultat.appels_modele, 0)

    def test_la_lettre_cochee_donne_le_type_derreur(self) -> None:
        resultat = diagnostiquer(
            niveau_test="3eme",
            reponses=[ReponseEleve(code_question="L5", contenu="a")],
        )
        probleme = resultat.problemes[0]
        self.assertEqual(probleme.code_competence, "L.IDR")
        self.assertEqual(probleme.code_type_erreur, "CPT")
        self.assertEqual(probleme.source, SourceProbleme.qcm)
        self.assertIn("4x^2 + 9", probleme.citation)

    def test_bonne_option_ne_produit_aucun_probleme(self) -> None:
        resultat = diagnostiquer(
            niveau_test="3eme",
            reponses=[ReponseEleve(code_question="L5", contenu="d")],
        )
        self.assertEqual(resultat.problemes, [])
        self.assertEqual(resultat.questions_ecartees, {})

    def test_qcm_non_coche_est_ecarte_pas_devine(self) -> None:
        """Aucune option ne décrit une case vide : rien ne s'en déduit.

        Le rattacher au hasard à `CNS` donnerait une lacune inventée, avec un
        coût, dans le palier d'un élève.
        """
        resultat = diagnostiquer(
            niveau_test="3eme",
            reponses=[ReponseEleve(code_question="L5", contenu="", vide=True)],
        )
        self.assertEqual(resultat.problemes, [])
        self.assertIn("L5", resultat.questions_ecartees)
        self.assertIn("enseignant", resultat.questions_ecartees["L5"])

    def test_reponse_ambigue_ecartee(self) -> None:
        """« b et c » n'est pas une réponse au QCM — un humain tranche."""
        resultat = diagnostiquer(
            niveau_test="3eme",
            reponses=[ReponseEleve(code_question="L5", contenu="b et c")],
        )
        self.assertEqual(resultat.problemes, [])
        self.assertIn("L5", resultat.questions_ecartees)

    def test_lecture_de_la_lettre(self) -> None:
        possibles = {"a", "b", "d"}
        for texte, attendu in [
            ("a", "a"),
            (" B ", "b"),
            ("(d)", "d"),
            ("b) 4x^2 - 6x + 9", "b"),
            ("c", None),          # option inexistante
            ("b et c", None),     # deux options
            ("", None),
            ("je ne sais pas", None),
        ]:
            with self.subTest(texte=texte):
                self.assertEqual(lettre_cochee(texte, possibles), attendu)


# ── Codes admissibles ────────────────────────────────────────────────────────


class TestCodesAdmis(BaseReferentiel):
    def test_les_prerequis_sont_admis(self) -> None:
        """Sans eux, `PRQ` serait inexprimable : ce type d'erreur désigne
        précisément une lacune en amont de la question posée."""
        admis = codes_competence_admis(self.courte)
        self.assertEqual(admis[0], "L.IDR")
        self.assertIn("L.DEV1", admis)

    def test_une_competence_etrangere_nest_pas_admise(self) -> None:
        self.assertNotIn("G.THA", codes_competence_admis(self.courte))


# ── Mise à l'écart ───────────────────────────────────────────────────────────


class TestQuestionsEcartees(BaseReferentiel):
    def test_construction_orientee_vers_lhumain(self) -> None:
        """Juger une perpendiculaire demande de mesurer la figure."""
        resultat = diagnostiquer(
            niveau_test="3eme",
            reponses=[ReponseEleve(code_question="G13", contenu="tracé")],
            client=ClientFactice([]),
        )
        self.assertIn("G13", resultat.questions_ecartees)
        self.assertIn("saisie humaine", resultat.questions_ecartees["G13"])

    def test_question_reussie_non_diagnostiquee(self) -> None:
        resultat = diagnostiquer(
            niveau_test="3eme",
            reponses=[ReponseEleve(code_question="L5", contenu="a", correcte=True)],
        )
        self.assertEqual(resultat.problemes, [])

    def test_sans_client_les_questions_ouvertes_sont_dites(self) -> None:
        """Le silence serait pris pour une réussite."""
        resultat = diagnostiquer(
            niveau_test="3eme",
            reponses=[
                ReponseEleve(code_question="L5", contenu="a"),
                ReponseEleve(code_question="L7", contenu="(x-5)^2"),
            ],
            client=None,
        )
        self.assertEqual(len(resultat.problemes), 1)  # le QCM seul
        self.assertIn("L7", resultat.questions_ecartees)

    def test_modele_muet_nefface_pas_les_questions(self) -> None:
        resultat = diagnostiquer(
            niveau_test="3eme",
            reponses=[ReponseEleve(code_question="L7", contenu="(x-5)^2")],
            client=ClientMuet(),
        )
        self.assertEqual(resultat.problemes, [])
        self.assertIn("429", resultat.questions_ecartees["L7"])

    def test_question_hors_referentiel(self) -> None:
        resultat = diagnostiquer(
            niveau_test="3eme",
            reponses=[ReponseEleve(code_question="ZZ99", contenu="x")],
        )
        self.assertIn("ZZ99", resultat.questions_ecartees)


# ── Ce que reçoit le modèle ──────────────────────────────────────────────────


class TestChargeUtile(BaseReferentiel):
    def test_les_signatures_sont_fournies(self) -> None:
        """« Le modèle reconnaît, il ne devine pas » — sans les signatures, il devine."""
        lot = preparer("3eme", [ReponseEleve(code_question="L7", contenu="(x-5)^2")])
        charge = lot.charge[0]
        self.assertEqual(charge["code_question"], "L7")
        self.assertEqual(len(charge["signatures_erreur"]), 1)
        self.assertEqual(charge["signatures_erreur"][0]["type_erreur"], "CPT")

    def test_une_zone_vierge_est_signalee_comme_telle(self) -> None:
        """« Pas de réponse » est une donnée de diagnostic, pas une absence de donnée."""
        lot = preparer("3eme", [ReponseEleve(code_question="L7", contenu="", vide=True)])
        self.assertTrue(lot.charge[0]["zone_vierge"])
        self.assertEqual(lot.charge[0]["reponse_eleve"], "(aucune réponse)")

    def test_les_qcm_ne_sont_pas_dans_la_charge(self) -> None:
        lot = preparer("3eme", [ReponseEleve(code_question="L5", contenu="a")])
        self.assertEqual(lot.charge, [])


# ── Validation et redemande ──────────────────────────────────────────────────


class TestValidation(BaseReferentiel):
    def _sortie(self, **champs) -> SortieDiagnosticContraint:
        defauts = {
            "code_question": "L7", "code_competence": "L.IDR",
            "code_type_erreur": "CPT", "citation": "(x-5)^2",
        }
        return SortieDiagnosticContraint(
            problemes=[ProblemeDetecte(**{**defauts, **champs})]
        )

    def test_code_de_competence_inconnu_refuse(self) -> None:
        retenus, rejets = valider(
            self._sortie(code_competence="L.INVENTE"),
            {"L7": {"L.IDR", "L.DEV1"}},
            {"CPT", "PRC"},
        )
        self.assertEqual(retenus, [])
        self.assertIn("L.INVENTE", rejets[0])

    def test_competence_valide_mais_etrangere_a_la_question_refusee(self) -> None:
        """Le trou que l'`enum` du schéma ne bouche pas : le code existe, il n'a
        simplement rien à faire sur cette question-là."""
        retenus, rejets = valider(
            self._sortie(code_competence="G.THA"),
            {"L7": {"L.IDR", "L.DEV1"}},
            {"CPT"},
        )
        self.assertEqual(retenus, [])
        self.assertIn("non admise", rejets[0])

    def test_type_derreur_inconnu_refuse(self) -> None:
        retenus, rejets = valider(
            self._sortie(code_type_erreur="XXX"), {"L7": {"L.IDR"}}, {"CPT"}
        )
        self.assertEqual(retenus, [])

    def test_citation_vide_refusee(self) -> None:
        """Sans citation, un désaccord avec le corpus est inarbitrable."""
        retenus, rejets = valider(
            self._sortie(citation="   "), {"L7": {"L.IDR"}}, {"CPT"}
        )
        self.assertEqual(retenus, [])
        self.assertIn("inarbitrable", rejets[0])

    def test_deux_problemes_sur_la_meme_question_refuses(self) -> None:
        sortie = SortieDiagnosticContraint(
            problemes=[
                ProblemeDetecte(code_question="L7", code_competence="L.IDR",
                                code_type_erreur="CPT", citation="a"),
                ProblemeDetecte(code_question="L7", code_competence="L.IDR",
                                code_type_erreur="PRC", citation="b"),
            ]
        )
        retenus, rejets = valider(sortie, {"L7": {"L.IDR"}}, {"CPT", "PRC"})
        self.assertEqual(len(retenus), 1)
        self.assertEqual(len(rejets), 1)

    def test_question_non_soumise_refusee(self) -> None:
        retenus, rejets = valider(
            self._sortie(code_question="L5"), {"L7": {"L.IDR"}}, {"CPT"}
        )
        self.assertEqual(retenus, [])


class TestRedemande(BaseReferentiel):
    def test_une_sortie_invalide_est_redemandee_puis_acceptee(self) -> None:
        client = ClientFactice([
            SortieDiagnosticContraint(problemes=[
                ProblemeDetecte(code_question="L7", code_competence="L.FANTOME",
                                code_type_erreur="CPT", citation="(x-5)^2"),
            ]),
            SortieDiagnosticContraint(problemes=[
                ProblemeDetecte(code_question="L7", code_competence="L.IDR",
                                code_type_erreur="CPT", citation="(x-5)^2"),
            ]),
        ])
        resultat = diagnostiquer(
            niveau_test="3eme",
            reponses=[ReponseEleve(code_question="L7", contenu="(x-5)^2")],
            client=client,
        )
        self.assertEqual(len(client.appels), 2)
        self.assertEqual(len(resultat.problemes), 1)
        self.assertEqual(resultat.rejets, [])
        self.assertTrue(resultat.valide)

    def test_la_redemande_porte_le_motif_du_refus(self) -> None:
        """On ne répare pas la sortie du modèle : on lui dit ce qui n'allait pas."""
        client = ClientFactice([
            SortieDiagnosticContraint(problemes=[
                ProblemeDetecte(code_question="L7", code_competence="L.FANTOME",
                                code_type_erreur="CPT", citation="x"),
            ]),
            SortieDiagnosticContraint(),
        ])
        diagnostiquer(
            niveau_test="3eme",
            reponses=[ReponseEleve(code_question="L7", contenu="x")],
            client=client,
        )
        self.assertEqual(client.appels[0]["corrections"], "")
        self.assertIn("L.FANTOME", client.appels[1]["corrections"])

    def test_ce_qui_reste_invalide_est_ecarte_jamais_repare(self) -> None:
        """Deux sorties fausses de suite : rien n'est écrit, et la copie ne
        compte pas comme sortie valide au jalon."""
        invalide = SortieDiagnosticContraint(problemes=[
            ProblemeDetecte(code_question="L7", code_competence="L.FANTOME",
                            code_type_erreur="CPT", citation="x"),
        ])
        client = ClientFactice([invalide, invalide])
        resultat = diagnostiquer(
            niveau_test="3eme",
            reponses=[ReponseEleve(code_question="L7", contenu="x")],
            client=client,
        )
        self.assertEqual(len(client.appels), 2)
        self.assertEqual(resultat.problemes, [])
        self.assertFalse(resultat.valide)
        self.assertIn("L7", resultat.questions_ecartees)

    def test_les_codes_soumis_au_modele_sont_ceux_du_referentiel(self) -> None:
        client = ClientFactice([SortieDiagnosticContraint()])
        diagnostiquer(
            niveau_test="3eme",
            reponses=[ReponseEleve(code_question="L7", contenu="x")],
            client=client,
        )
        appel = client.appels[0]
        self.assertEqual(sorted(appel["codes_types"]), ["ATT", "CPT", "PRC"])
        self.assertEqual(sorted(appel["codes_competences"]), ["L.DEV1", "L.IDR"])


# ── Mesure plancher : diagnostic sans ancrage de question ────────────────────


class ClientPlancherFactice(ClientFactice):
    """Même carnet d'appels, mais sur la méthode du mode sans ancrage."""

    def diagnose_unanchored(self, **kwargs) -> ClaudeResponse:
        return self.diagnose_constrained(**kwargs)


class TestSansAncrage(BaseReferentiel):
    def test_le_catalogue_sarrete_au_niveau_du_test(self) -> None:
        """Un test d'entrée **en** 3ème évalue ce qui précède la 3ème.

        Sans cette borne, le modèle se verrait proposer des compétences que
        l'élève n'a pas encore rencontrées — un échec y serait normal et le
        diagnostic facturerait une lacune inexistante.
        """
        codes = {c["code"] for c in catalogue_competences("3eme")}
        self.assertIn("L.IDR", codes)    # introduite en 4ème, déjà vue
        self.assertIn("L.DEV1", codes)   # introduite en 5ème, déjà vue

        # Pour une entrée **en** 5ème, une compétence introduite en 5ème n'a pas
        # encore été enseignée : l'égalité compte comme « pas encore vue ».
        codes_5e = {c["code"] for c in catalogue_competences("5eme")}
        self.assertNotIn("L.DEV1", codes_5e)
        self.assertNotIn("L.IDR", codes_5e)

    def test_aucune_signature_nest_fournie(self) -> None:
        """C'est ce qui fait de cette mesure un plancher : le modèle n'a rien à
        reconnaître, il doit juger sur la seule production."""
        client = ClientPlancherFactice([SortieDiagnosticContraint()])
        diagnostiquer_sans_ancrage(
            niveau_test="3eme",
            productions=[
                ProductionEleve(repere="ex 3b", enonce="Factoriser x^2-25",
                                production="(x-5)^2"),
            ],
            client=client,
            copy_id="CORPUS-3E-01",
        )
        appel = client.appels[0]
        self.assertNotIn("signatures_erreur", appel["productions"][0])
        self.assertEqual(appel["productions"][0]["repere"], "ex 3b")

    def test_une_competence_hors_catalogue_est_refusee(self) -> None:
        hors_catalogue = SortieDiagnosticContraint(problemes=[
            ProblemeDetecte(code_question="ex 3b", code_competence="L.FANTOME",
                            code_type_erreur="CPT", citation="(x-5)^2"),
        ])
        client = ClientPlancherFactice([hors_catalogue, hors_catalogue])
        resultat = diagnostiquer_sans_ancrage(
            niveau_test="3eme",
            productions=[
                ProductionEleve(repere="ex 3b", enonce="Factoriser x^2-25",
                                production="(x-5)^2"),
            ],
            client=client,
            copy_id="CORPUS-3E-01",
        )
        self.assertEqual(resultat.problemes, [])
        self.assertFalse(resultat.valide)
        self.assertEqual(len(client.appels), 2)  # redemandé une fois

    def test_une_production_vierge_reste_soumise(self) -> None:
        """« Rien écrit » est une donnée de diagnostic — le plus souvent CNS."""
        client = ClientPlancherFactice([SortieDiagnosticContraint()])
        diagnostiquer_sans_ancrage(
            niveau_test="3eme",
            productions=[ProductionEleve(repere="ex 4", enonce="…", production="  ")],
            client=client,
        )
        production = client.appels[0]["productions"][0]
        self.assertTrue(production["zone_vierge"])
        self.assertEqual(production["production_eleve"], "(aucune réponse)")
