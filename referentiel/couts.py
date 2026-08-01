"""
Calcul du coût de remédiation, et volume de repli pour le lycée.

La formule vient du protocole (§4) :

    coût = volume horaire officiel × coefficient du type d'erreur

**arrondi à l'heure entière supérieure**, plancher 1 h, plafond 4 h par problème.
Le plafond évite qu'un seul problème absorbe la moitié d'un plan de remédiation.

Pourquoi l'entier supérieur, et ce que ça coûte
-----------------------------------------------
Décision utilisateur du 2026-08-01 : plus de demi-heures, on arrondit toujours
au-dessus (1,5 → 2). Une séance de remédiation ne se découpe pas en trente
minutes sur le terrain, et arrondir vers le bas revient à promettre un volume
qu'on ne tiendra pas.

Deux conséquences à connaître, parce qu'elles ne sont pas neutres :

1. **L'échelle se resserre.** Les coûts ne prennent plus que quatre valeurs
   (1, 2, 3, 4 h) au lieu de huit. Sur les 27 compétences de lycée, dont le
   volume de repli est 4 h, quatre des six types remédiables (`CNS`, `PRC`,
   `RED`, `MOD`) tombent tous sur 1 h : le type d'erreur n'y départage plus rien.
   C'est le même effet de dégénérescence que le repli à 20 h avait produit par le
   haut (voir plus bas), cette fois par le bas.
2. **Les coûts montent, donc les paliers glissent.** Tout ce qui valait 0,5 h
   vaut désormais 1 h, et le plancher double. Des élèves classés palier A
   (< 8 h) passeront en B. Le seuil A/B/C n'a pas été rejugé en même temps : à
   surveiller sur les premières sessions réelles.

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

from decimal import ROUND_CEILING, Decimal

#: Volume horaire de repli, en heures — médiane des volumes réels du collège.
VOLUME_REPLI_LYCEE = Decimal("4")

#: Bornes du protocole (§4). Plancher relevé à 1 h avec l'arrondi à l'entier
#: supérieur : un coût remédiable ne peut plus valoir une demi-heure.
COUT_PLANCHER = Decimal("1")
COUT_PLAFOND = Decimal("4")


def arrondir_heures(valeur: Decimal) -> Decimal:
    """Ramène un coût à l'heure entière supérieure, dans les bornes du protocole.

    Point de passage **unique** de la règle « pas de demi-heure, toujours au
    dessus ». Il existe parce que la grille a deux sources, et que la règle
    doit valoir pour les deux :

    - les **444 coûts officiels** viennent du classeur, lus tels quels — le
      classeur est la source de vérité (arbitrage G) et arrondissait, lui, à la
      demi-heure ;
    - les **162 coûts de lycée** sont calculés ici par `cout_remediation()`
      depuis le volume de repli.

    Avant le 2026-08-01, `cout_remediation()` portait seule la règle d'arrondi
    et n'était appelée que sur la seconde voie : **73 % de la grille ne la
    voyait jamais passer.** Changer la formule sans ce point de passage n'aurait
    donc corrigé que 162 lignes sur 606, en silence.

    Un coût nul reste nul : c'est `ATT`, qui n'est pas remédiable.
    """
    valeur = Decimal(valeur)
    if valeur <= 0:
        return Decimal("0")
    entier = valeur.to_integral_value(rounding=ROUND_CEILING)
    return max(COUT_PLANCHER, min(COUT_PLAFOND, entier))


def cout_precalcule(code_competence: str, code_type_erreur: str) -> Decimal:
    """Coût d'un couple compétence × type d'erreur, lu dans `CoutRemediation`.

    **Une ligne absente n'est pas une anomalie** : `ATT` n'en a aucune par
    construction — l'inattention ne donne jamais lieu à remédiation. Renvoyer 0
    plutôt que lever est donc le comportement juste, et c'est la raison d'être de
    cette fonction : chaque appelant qui referait la lecture à la main
    retomberait sur ce piège, et un `DoesNotExist` sur un cas parfaitement normal
    ferait échouer un tagage ou un diagnostic entier.
    """
    from referentiel.models import CoutRemediation

    ligne = CoutRemediation.objects.filter(
        competence_id=code_competence, type_erreur_id=code_type_erreur
    ).first()
    return ligne.cout_heures if ligne else Decimal("0")


def cout_remediation(volume_horaire: Decimal, coefficient: Decimal) -> Decimal:
    """Coût d'un problème, arrondi à l'heure entière supérieure, borné.

    L'arrondi va **toujours vers le haut**, jamais au plus proche : 1,1 h comme
    1,9 h donnent 2 h. Arrondir vers le bas reviendrait à inscrire un volume
    qu'on sait insuffisant.

    Un coefficient nul — c'est le cas d'`ATT`, l'inattention — donne 0 et non le
    plancher : ce type d'erreur ne donne jamais lieu à remédiation, lui attribuer
    une heure reviendrait à facturer une étourderie. C'est le seul cas où le
    résultat sort de l'intervalle [plancher, plafond], et il est délibéré.
    """
    if coefficient <= 0:
        return Decimal("0")

    return arrondir_heures(Decimal(volume_horaire) * Decimal(coefficient))
