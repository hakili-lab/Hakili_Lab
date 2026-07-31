"""
Le plan de remédiation : quoi travailler, dans quel ordre, combien d'heures.

L'ordre n'est pas cosmétique
----------------------------
« Un problème dont un prérequis est lui-même en difficulté se traite **après** ce
prérequis, jamais avant » (protocole §3). C'est ce qui distingue une remédiation
d'un rattrapage : on remonte à la cause au lieu de soigner le symptôme. Travailler
les identités remarquables avec un élève qui ne sait pas additionner deux relatifs
est du temps perdu, et le tuteur le découvrirait en séance.

L'ordonnancement est donc un **tri topologique** sur le graphe des prérequis,
restreint aux compétences réellement en difficulté. À égalité, on commence par le
plus fondamental — la compétence introduite le plus tôt dans la scolarité.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from suivi.models import EtatProbleme

#: Ordre scolaire, pour départager deux problèmes également prioritaires.
_ORDRE_NIVEAUX = [
    "Primaire", "6eme", "5eme", "4eme", "3eme", "2ndeC", "1ereD",
]


@dataclass
class EtapePlan:
    """Un problème à traiter, avec de quoi préparer la séance."""

    probleme: object
    rang: int
    cout: Decimal
    prerequis_aussi_en_difficulte: list = field(default_factory=list)
    signatures: list = field(default_factory=list)

    @property
    def competence(self):
        return self.probleme.competence

    @property
    def type_erreur(self):
        return self.probleme.type_erreur


def _niveau(competence) -> int:
    try:
        return _ORDRE_NIVEAUX.index(competence.niveau_intro)
    except ValueError:
        return len(_ORDRE_NIVEAUX)


def ordonner(problemes: list) -> list[EtapePlan]:
    """Trie les problèmes pour que chaque prérequis en difficulté vienne avant.

    Tri topologique par couches : à chaque tour on sort les problèmes dont aucun
    prérequis n'est encore à traiter. Si le graphe contenait un cycle — la base
    l'interdit, mais un import mal formé pourrait en créer un — on sort le reste
    tel quel plutôt que de boucler indéfiniment.
    """
    par_code = {p.competence.code: p for p in problemes}
    restants = dict(par_code)
    dependances = {
        code: {
            lien.prerequis_id
            for lien in probleme.competence.prerequis.all()
            if lien.prerequis_id in par_code
        }
        for code, probleme in par_code.items()
    }

    ordonnes: list = []
    traites: set[str] = set()

    while restants:
        prets = [
            code for code in restants if not (dependances[code] - traites)
        ]
        if not prets:
            # Cycle : on verse le reste par niveau plutôt que de boucler.
            prets = list(restants)

        prets.sort(key=lambda c: (_niveau(restants[c].competence), c))
        for code in prets:
            ordonnes.append(restants.pop(code))
            traites.add(code)

    return ordonnes


def construire(session) -> dict:
    """Plan complet d'une session : étapes ordonnées, coût, palier.

    N'inclut que les problèmes **confirmés** ou déjà **en remédiation** : une
    hypothèse non vérifiée n'a rien à faire dans un plan de travail, c'est tout
    l'objet du test de confirmation.
    """
    problemes = list(
        session.problemes.filter(
            etat__in=[EtatProbleme.CONFIRME, EtatProbleme.EN_REMEDIATION]
        )
        .select_related("competence", "type_erreur")
        .prefetch_related("competence__prerequis__prerequis")
    )

    codes_en_difficulte = {p.competence.code for p in problemes}
    etapes: list[EtapePlan] = []

    for rang, probleme in enumerate(ordonner(problemes), start=1):
        prerequis_bloquants = [
            lien.prerequis
            for lien in probleme.competence.prerequis.all()
            if lien.prerequis_id in codes_en_difficulte
        ]
        etapes.append(
            EtapePlan(
                probleme=probleme,
                rang=rang,
                cout=probleme.cout_estime,
                prerequis_aussi_en_difficulte=prerequis_bloquants,
                signatures=_signatures(probleme),
            )
        )

    total = sum((e.cout for e in etapes), Decimal("0"))
    return {
        "etapes": etapes,
        "total_heures": total,
        "palier": session.calculer_palier() if etapes else "",
        "nb_problemes": len(etapes),
        "repose_sur_estimation": any(
            e.probleme.competence.volume_estime for e in etapes
        ),
    }


def _signatures(probleme) -> list:
    """Ce que l'élève a probablement écrit, et ce que ça révèle.

    Matière concrète pour le tuteur : les signatures viennent du référentiel et
    décrivent l'erreur observable, pas une généralité sur la compétence. On se
    limite au type d'erreur diagnostiqué — les autres décriraient une difficulté
    que cet élève n'a pas.
    """
    from referentiel.models import SignatureErreur

    return list(
        SignatureErreur.objects.filter(
            competence_id=probleme.competence_id,
            type_erreur_id=probleme.type_erreur_id,
        ).select_related("question")[:4]
    )
