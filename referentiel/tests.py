"""
Tests du calcul de coût de remédiation et du volume de repli.

Ces valeurs déterminent le **palier** d'un élève — donc le nombre d'heures qu'une
famille paiera et le format de son parcours. Une régression ici ne se verrait pas
à l'écran : elle produirait des plans de remédiation faux, avec l'air d'être justes.
"""
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from referentiel.couts import (
    COUT_PLAFOND,
    COUT_PLANCHER,
    VOLUME_REPLI_LYCEE,
    cout_remediation,
)
from referentiel.models import Competence, CoutRemediation, TypeErreur

# Coefficients réels du protocole (§3).
_COEFFICIENTS = {
    "PRQ": Decimal("0.50"), "CPT": Decimal("0.35"), "MOD": Decimal("0.25"),
    "PRC": Decimal("0.15"), "RED": Decimal("0.15"), "CNS": Decimal("0.10"),
    "ATT": Decimal("0.00"),
}


class TestFormuleCout(TestCase):
    def test_arrondi_a_l_entier_superieur(self) -> None:
        # 4 h x 0,35 = 1,40 → 2 h
        self.assertEqual(cout_remediation(Decimal(4), Decimal("0.35")), Decimal("2"))
        # 4 h x 0,15 = 0,60 → 1 h
        self.assertEqual(cout_remediation(Decimal(4), Decimal("0.15")), Decimal("1"))

    def test_l_arrondi_va_toujours_vers_le_haut(self) -> None:
        """Et non au plus proche : c'est toute la différence avec la règle
        précédente. 6 h x 0,35 = 2,10 valait 2 h à la demi-heure ; il vaut 3 h
        désormais. Un plan de remédiation ne se tient pas en promettant moins
        d'heures qu'il n'en faut."""
        self.assertEqual(cout_remediation(Decimal(6), Decimal("0.35")), Decimal("3"))
        self.assertEqual(cout_remediation(Decimal(2), Decimal("0.55")), Decimal("2"))

    def test_aucun_cout_remediable_n_est_fractionnaire(self) -> None:
        """La règle porte sur toute la grille, pas sur quelques cas : aucun coût
        ne doit sortir avec une partie décimale."""
        for volume in (Decimal("1.5"), Decimal("4"), Decimal("7.5"), Decimal("20.5")):
            for coefficient in _COEFFICIENTS.values():
                cout = cout_remediation(volume, coefficient)
                self.assertEqual(
                    cout, cout.to_integral_value(),
                    f"{volume} h x {coefficient} donne {cout}, qui n'est pas entier",
                )

    def test_plancher(self) -> None:
        """Un problème confirmé demande au moins une heure : une demi-heure de
        séance n'existe pas sur le terrain."""
        self.assertEqual(
            cout_remediation(Decimal("1.5"), Decimal("0.10")), COUT_PLANCHER
        )
        self.assertEqual(COUT_PLANCHER, Decimal("1"))

    def test_plafond(self) -> None:
        """Le plafond évite qu'un seul problème absorbe la moitié d'un plan."""
        self.assertEqual(
            cout_remediation(Decimal("20.5"), Decimal("0.50")), COUT_PLAFOND
        )

    def test_att_vaut_zero_et_non_le_plancher(self) -> None:
        """`ATT` existe pour être écarté. Lui donner une heure reviendrait à
        facturer une étourderie à une famille."""
        self.assertEqual(cout_remediation(Decimal(4), Decimal("0")), Decimal("0"))

    def test_le_repli_lycee_ne_departage_plus_que_deux_types(self) -> None:
        """⚠ Constat, pas un objectif — l'arrondi à l'entier supérieur a coûté ça.

        Ce test vérifiait auparavant que le repli à 4 h gardait `PRQ`, `CPT` et
        `MOD` sur trois valeurs distinctes (2 / 1,5 / 1 h) : c'était la raison
        même du choix de 4 h plutôt que 20 h. Avec l'arrondi vers le haut, les
        six types remédiables ne prennent plus que **deux** valeurs sur le lycée
        — 2 h pour `PRQ` et `CPT`, 1 h pour les quatre autres. Le type d'erreur
        n'y départage donc presque plus rien.

        Ce n'est pas un test qu'on fait passer, c'est un constat qu'on garde
        sous les yeux : le jour où les vrais volumes horaires du lycée
        arriveront (arbitrage E), la question redeviendra sans objet. D'ici là,
        un plan de remédiation de lycée est chiffré plus grossièrement qu'un
        plan de collège, et personne ne doit le découvrir sur une facture.
        """
        couts = {
            code: cout_remediation(VOLUME_REPLI_LYCEE, coef)
            for code, coef in _COEFFICIENTS.items()
            if coef > 0
        }
        self.assertEqual(couts["PRQ"], Decimal("2"))
        self.assertEqual(couts["CPT"], Decimal("2"))
        self.assertEqual(couts["MOD"], Decimal("1"))
        self.assertEqual(couts["CNS"], Decimal("1"))
        self.assertEqual(len(set(couts.values())), 2)

    def test_un_repli_a_20h_serait_degenere(self) -> None:
        """Test de garde : documente pourquoi 20 h a été écarté. Si quelqu'un
        relève `VOLUME_REPLI_LYCEE`, ce test rappelle l'effet du plafond."""
        couts = {
            code: cout_remediation(Decimal(20), coef)
            for code in ("PRQ", "CPT", "MOD")
            for coef in [_COEFFICIENTS[code]]
        }
        self.assertEqual(set(couts.values()), {COUT_PLAFOND})


class TestCoutsEstimes(TestCase):
    """Les 27 compétences de lycée n'ont pas de volume officiel : sans coût estimé,
    le palier d'un élève de 2nde ou de 1ère resterait indéterminable."""

    @classmethod
    def setUpTestData(cls) -> None:
        for code, coef in _COEFFICIENTS.items():
            TypeErreur.objects.create(
                code=code, libelle=code, definition="…", signature="…",
                coefficient=coef, remediable=coef > 0,
            )
        cls.college = Competence.objects.create(
            code="L.IDR", domaine="Calcul litteral et algebre", libelle="Identités",
            niveau_intro="4eme", volume_horaire=Decimal("2"), volume_estime=False,
        )
        cls.lycee = Competence.objects.create(
            code="F.DER", domaine="Fonctions et applications", libelle="Dérivation",
            niveau_intro="1ereD", volume_horaire=VOLUME_REPLI_LYCEE, volume_estime=True,
        )

    def test_volume_estime_est_signale(self) -> None:
        """Un coût estimé ne doit jamais être confondu avec un chiffre du curriculum."""
        self.assertFalse(self.college.volume_estime)
        self.assertTrue(self.lycee.volume_estime)

    def test_couts_calculables_pour_le_lycee(self) -> None:
        remediables = TypeErreur.objects.filter(coefficient__gt=0)
        for type_erreur in remediables:
            CoutRemediation.objects.create(
                competence=self.lycee,
                type_erreur=type_erreur,
                cout_heures=cout_remediation(
                    self.lycee.volume_horaire, type_erreur.coefficient
                ),
                estime=True,
            )
        self.assertEqual(self.lycee.couts.count(), 6)
        self.assertTrue(all(c.estime for c in self.lycee.couts.all()))

    def test_att_reste_sans_ligne_de_cout(self) -> None:
        """Même avec un volume de repli : `ATT` n'est pas remédiable, il ne doit
        pas apparaître dans la table des coûts."""
        remediables = TypeErreur.objects.filter(coefficient__gt=0)
        self.assertEqual(remediables.count(), 6)
        self.assertNotIn("ATT", [t.code for t in remediables])

    def test_palier_calculable(self) -> None:
        """Deux problèmes PRQ de lycée = 4 h → palier A. Avec un repli à 20 h,
        les mêmes deux problèmes auraient donné 8 h, soit déjà le palier B."""
        prq = TypeErreur.objects.get(code="PRQ")
        cout = cout_remediation(self.lycee.volume_horaire, prq.coefficient)
        self.assertEqual(cout * 2, Decimal("4.0"))
        self.assertLess(cout * 2, Decimal(8))  # sous le seuil du palier B
