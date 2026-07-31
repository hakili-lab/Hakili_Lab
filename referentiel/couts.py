"""
Calcul du coût de remédiation, et volume de repli pour le lycée.

La formule vient du protocole (§4) :

    coût = volume horaire officiel × coefficient du type d'erreur

arrondi à la demi-heure, plancher 0,5 h, plafond 4 h par problème. Le plafond
évite qu'un seul problème absorbe la moitié d'un plan de remédiation.

Le volume de repli, et pourquoi 4 h
-----------------------------------
Les 27 compétences du lycée n'ont pas de volume horaire : les documents officiels
du secondaire ne donnent qu'une progression mensuelle, pas un volume par chapitre.
Sans volume, aucun coût n'est calculable, donc le palier A/B/C d'un élève de 2nde
ou de 1ère reste indéterminable — le dispositif ne peut pas tourner sur ces niveaux.

**4 h est la médiane des 74 volumes réels du collège** (moyenne 5,3 h, étendue de
1,5 à 20,5 h). Cette valeur a été retenue après avoir calculé l'effet d'un repli à
20 h, qui rendait le dispositif dégénéré : le plafond de 4 h écrasait `PRQ`, `CPT`
et `MOD` à la même valeur, rendant le type d'erreur sans effet sur tout le lycée,
et deux problèmes confirmés suffisaient à basculer en palier B.

Avec 4 h, les six types remédiables gardent des coûts distincts (2 h, 1,5 h, 1 h,
0,5 h, 0,5 h, 0,5 h) et les paliers conservent leur sens.

C'est une **estimation, pas une donnée officielle**. Elle est marquée comme telle
en base (`Competence.volume_estime`, `CoutRemediation.estime`) pour qu'un coût
estimé ne soit jamais confondu avec un coût dérivé du curriculum, et pour que le
remplacement soit trivial le jour où les vrais volumes seront connus.
"""
from __future__ import annotations

from decimal import Decimal

#: Volume horaire de repli, en heures — médiane des volumes réels du collège.
VOLUME_REPLI_LYCEE = Decimal("4")

#: Bornes du protocole (§4).
COUT_PLANCHER = Decimal("0.5")
COUT_PLAFOND = Decimal("4")


def cout_remediation(volume_horaire: Decimal, coefficient: Decimal) -> Decimal:
    """Coût d'un problème, arrondi à la demi-heure, borné.

    Un coefficient nul — c'est le cas d'`ATT`, l'inattention — donne 0 et non le
    plancher : ce type d'erreur ne donne jamais lieu à remédiation, lui attribuer
    une demi-heure reviendrait à facturer une étourderie.
    """
    if coefficient <= 0:
        return Decimal("0")

    brut = Decimal(volume_horaire) * Decimal(coefficient)
    demi_heures = (brut * 2).quantize(Decimal("1"))  # arrondi au plus proche
    arrondi = demi_heures / 2
    return max(COUT_PLANCHER, min(COUT_PLAFOND, arrondi))
