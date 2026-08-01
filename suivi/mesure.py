"""
Mesure du module 4 contre le corpus de référence.

Le jalon du chantier est explicite : « écart mesuré et consigné entre le
diagnostic automatique et le tagage manuel du corpus ». Ce fichier calcule cet
écart. Il ne juge pas, il compte — et il compte trois choses qui ne se valent pas.

Les trois catégories, et pourquoi la deuxième compte le plus
------------------------------------------------------------
· **Exact** — même compétence, même type d'erreur. Le diagnostic tombe juste.
· **Compétence juste, type faux** — c'est le cas instructif. Le corpus en porte
  la démonstration : périmètre d'une table circulaire, `1,3 × 2` (formule absente,
  `CNS`) contre `1,3 × 3,14 = 1,2856` (formule juste, produit faux, `PRC`). Même
  compétence, deux remédiations sans rapport. Un diagnostic qui trouve la
  compétence et rate le type envoie le tuteur travailler la mauvaise chose ; il
  est moins faux qu'un hors-sujet, mais il n'est pas juste.
· **Manqué / en trop** — lacune non vue, ou inventée.

Pourquoi l'écart de coût figure ici
-----------------------------------
Le coût détermine le palier, donc ce qu'une famille paie et ce qu'on lui promet.
Un diagnostic à 80 % de rappel qui rate systématiquement les problèmes chers ne
vaut pas un diagnostic à 80 % qui rate les petits. La précision seule ne le dit
pas ; l'écart d'heures, si.

Une limite à garder en tête
---------------------------
Le corpus est constitué de copies de l'**ancien format**, qui ne portent aucune
des 280 questions Urie. Il ne contient par ailleurs ni `PRQ` ni `RED` (voir la
fiche du module 3) : sur ces deux types, la mesure ne dit rien — ni en bien ni
en mal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from referentiel.couts import cout_precalcule

#: Un couple compétence × type d'erreur.
Couple = tuple[str, str]


@dataclass
class Ecart:
    """Le résultat d'une comparaison — des listes, pas seulement des taux.

    Les couples sont conservés en clair : un taux ne se discute pas, une liste
    de désaccords si. C'est ce qui permet de trancher lequel des deux a raison,
    le corpus ou le module 4 — et parfois c'est le corpus.
    """

    exacts: list[Couple] = field(default_factory=list)
    #: compétence trouvée, type d'erreur différent → (compétence, type étalon, type produit)
    type_faux: list[tuple[str, str, str]] = field(default_factory=list)
    manques: list[Couple] = field(default_factory=list)
    en_trop: list[Couple] = field(default_factory=list)
    cout_etalon: Decimal = Decimal("0")
    cout_produit: Decimal = Decimal("0")

    @property
    def total_etalon(self) -> int:
        return len(self.exacts) + len(self.type_faux) + len(self.manques)

    @property
    def total_produit(self) -> int:
        return len(self.exacts) + len(self.type_faux) + len(self.en_trop)

    @property
    def precision(self) -> float:
        """Part des problèmes produits qui sont exacts."""
        return len(self.exacts) / self.total_produit if self.total_produit else 0.0

    @property
    def rappel(self) -> float:
        """Part des problèmes de l'étalon retrouvés exactement."""
        return len(self.exacts) / self.total_etalon if self.total_etalon else 0.0

    @property
    def rappel_competence(self) -> float:
        """Part de l'étalon dont la compétence a été trouvée, type juste ou non.

        Distingué du rappel exact à dessein : une compétence trouvée avec le
        mauvais type reste une lacune détectée, que T1 peut trancher. Une
        compétence manquée ne sera jamais posée à l'élève.
        """
        trouves = len(self.exacts) + len(self.type_faux)
        return trouves / self.total_etalon if self.total_etalon else 0.0

    @property
    def ecart_cout(self) -> Decimal:
        """Heures produites moins heures de l'étalon. Positif = surestimation."""
        return self.cout_produit - self.cout_etalon


def _cout(couples: list[Couple]) -> Decimal:
    return sum((cout_precalcule(c, t) for c, t in couples), Decimal("0"))


def comparer(etalon: list[Couple], produit: list[Couple]) -> Ecart:
    """Compare deux jeux de problèmes, sans tenir compte de l'ordre.

    Les doublons sont écrasés : la base n'accepte qu'un couple par session, les
    compter deux fois n'aurait pas de sens.
    """
    restants_etalon = dict.fromkeys(etalon)
    restants_produit = dict.fromkeys(produit)
    ecart = Ecart(
        cout_etalon=_cout(list(restants_etalon)),
        cout_produit=_cout(list(restants_produit)),
    )

    # 1. Les correspondances exactes d'abord — elles ne doivent pas être
    #    consommées par un appariement approximatif sur la compétence.
    for couple in list(restants_etalon):
        if couple in restants_produit:
            ecart.exacts.append(couple)
            del restants_etalon[couple]
            del restants_produit[couple]

    # 2. Puis, sur ce qui reste, les compétences communes.
    for couple in list(restants_etalon):
        competence, type_etalon = couple
        jumeau = next(
            (c for c in restants_produit if c[0] == competence), None
        )
        if jumeau is not None:
            ecart.type_faux.append((competence, type_etalon, jumeau[1]))
            del restants_etalon[couple]
            del restants_produit[jumeau]

    ecart.manques.extend(restants_etalon)
    ecart.en_trop.extend(restants_produit)
    return ecart


def repartition_par_type(couples: list[Couple]) -> dict[str, int]:
    """Combien de problèmes par type d'erreur — pour voir *où* ça diverge."""
    compte: dict[str, int] = {}
    for _, type_erreur in dict.fromkeys(couples):
        compte[type_erreur] = compte.get(type_erreur, 0) + 1
    return dict(sorted(compte.items(), key=lambda kv: (-kv[1], kv[0])))
