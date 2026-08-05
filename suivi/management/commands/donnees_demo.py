"""Parcours de démonstration pour les élèves factices — développement uniquement.

Le jeu factice de `src/integrations/sheets_factices.py` remplit les écrans qui
listent des élèves. Il ne suffit pas pour `/parcours/<jeton>/`, l'écran le plus
riche du chantier Urie v2 : celui-ci a besoin d'une `Session`, de `Problème`s et
de leurs `Transition`s. Cette commande les crée.

Trois précautions, chacune pour une raison précise
--------------------------------------------------
1. **Refuse de tourner hors `DEBUG`.** Ces sessions porteraient un palier et un
   coût — donc, sur un vrai dossier, un devis. Elles n'ont rien à faire en
   production.
2. **Ne touche jamais au corpus de référence.** Les cinq sessions `CORPUS-*`
   sont l'étalon du module 4 ; les modifier ferait bouger la mesure sans que le
   compte rendu le dise. La commande ne travaille que sur les identifiants
   qu'elle a elle-même créés.
3. **Idempotente.** Rejouée, elle repart de zéro sur ses propres sessions plutôt
   que d'empiler des doublons — un problème compté deux fois fausse le coût,
   donc le palier.

Les états sont atteints par `changer_etat()`, jamais en écrivant `etat`
directement : c'est ce qui garantit que chaque `Transition` existe, et l'écran
de parcours comme les indicateurs du module 9 s'appuient dessus.

Usage
-----
    $env:DEBUG="true"; python manage.py donnees_demo
    $env:DEBUG="true"; python manage.py donnees_demo --supprimer
"""
from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from referentiel.couts import cout_precalcule
from referentiel.models import Competence, TypeErreur
from suivi.models import (
    EtatProbleme,
    EtatSession,
    Evaluation,
    Probleme,
    Session,
    TypeEvaluation,
)

#: Marqueur porté par les sessions de cette commande. Sert à les retrouver pour
#: les remplacer ou les supprimer, sans jamais risquer d'attraper une session
#: réelle ou une session du corpus.
PREFIXE = "demo_"


def _identifiant(nom: str, prenom: str, contact: str) -> str:
    """Même construction que `build_identifiant_hakili`, réutilisée telle quelle.

    Importée plutôt que recopiée : si la règle de composition change, ces
    sessions doivent suivre, sinon elles cesseraient silencieusement de
    correspondre aux élèves du jeu factice et les parcours deviendraient
    introuvables.
    """
    from src.integrations.google_sheets import build_identifiant_hakili

    return build_identifiant_hakili(nom, prenom, contact)


#: Trois parcours choisis pour montrer trois états différents de l'écran, pas
#: trois variantes du même : sans eux on ne verrait jamais qu'un seul cas.
#:
#:   · TRAORE Adama   — plan établi, en attente d'inscription (le bouton s'affiche)
#:   · ZONGO Mariam   — déjà inscrite en remédiation (le bouton a disparu)
#:   · BANCE Yacouba  — palier C, hors dispositif (`inscrire()` refuse sans motif)
_PARCOURS: list[dict] = [
    {
        "eleve": ("TRAORE", "Adama", "70 00 00 06"),
        "etat_session": EtatSession.ATTENTE_INSCRIPTION,
        "type_evaluation": TypeEvaluation.T1,
        # (compétence, type d'erreur, état visé, ce qui a été lu sur la copie)
        "problemes": [
            ("N.ENS", "CPT", EtatProbleme.CONFIRME,
             "Place -3 à droite de -1 sur la droite graduée."),
            ("L.IDR", "CPT", EtatProbleme.CONFIRME,
             "Développe (2x-3)² en 4x² + 9 : le double produit est absent."),
            ("L.EQ1", "PRC", EtatProbleme.CONFIRME,
             "Pose correctement puis se trompe de signe en passant le terme."),
            ("G.PYT", "CNS", EtatProbleme.HYPOTHESE,
             "Écrit le théorème avec la somme des trois côtés."),
            # ATT n'a aucune ligne de coût par construction : le problème vaut 0 h
            # et ne peut jamais quitter `hypothese` autrement que vers `ecarte`.
            # Sa présence ici vérifie que l'écran ne le facture pas.
            ("N.FRA2", "ATT", EtatProbleme.HYPOTHESE,
             "Résultat juste au brouillon, recopié faux."),
        ],
    },
    {
        "eleve": ("ZONGO", "Mariam", "70 00 00 04"),
        "etat_session": EtatSession.REMEDIATION,
        "type_evaluation": TypeEvaluation.T1,
        "problemes": [
            ("N.DIVIS", "CNS", EtatProbleme.EN_REMEDIATION,
             "Ne connaît aucun critère de divisibilité."),
            ("G.SYMC", "MOD", EtatProbleme.EN_REMEDIATION,
             "Construit le symétrique sans repérer le centre."),
            ("N.FRA2", "PRC", EtatProbleme.CONFIRME,
             "Additionne numérateurs et dénominateurs séparément."),
        ],
    },
    {
        # Palier C : plus de 20 h cumulées. Le cas compte parce qu'il est le seul
        # où `inscrire()` refuse sans motif tracé (D-CEO-34) — un écran testé
        # uniquement sur des paliers A et B ne montrerait jamais ce refus.
        # Six prérequis manquants à 4 h, le plafond de la grille : 24 h.
        "eleve": ("BANCE", "Yacouba", "70 00 00 08"),
        "etat_session": EtatSession.ATTENTE_INSCRIPTION,
        "type_evaluation": TypeEvaluation.T1,
        "problemes": [
            ("N.ENS", "PRQ", EtatProbleme.CONFIRME, "Les ensembles de nombres ne sont pas en place."),
            ("N.RAT", "PRQ", EtatProbleme.CONFIRME, "Aucun calcul sur les rationnels n'aboutit."),
            ("N.DIVIS", "PRQ", EtatProbleme.CONFIRME, "Multiples et diviseurs confondus."),
            ("L.SYS", "PRQ", EtatProbleme.CONFIRME, "Ne sait pas isoler une inconnue."),
            ("G.MED", "PRQ", EtatProbleme.CONFIRME, "Droites remarquables non identifiées."),
            ("G.PARAL", "PRQ", EtatProbleme.CONFIRME, "Parallélisme jamais utilisé dans une preuve."),
            ("L.IDR", "CPT", EtatProbleme.CONFIRME, "Aucune identité remarquable reconnue."),
        ],
    },
]


class Command(BaseCommand):
    help = "Crée des parcours de démonstration pour les élèves factices (DEBUG uniquement)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--supprimer",
            action="store_true",
            help="Retire les sessions de démonstration et s'arrête.",
        )

    def handle(self, *args, **options) -> None:
        if not settings.DEBUG:
            raise CommandError(
                "donnees_demo ne tourne qu'en DEBUG. Ces sessions portent un palier "
                "et un coût : hors développement, elles ressembleraient à des dossiers "
                "réels."
            )

        identifiants = [_identifiant(*p["eleve"]) for p in _PARCOURS]
        existantes = Session.objects.filter(
            identifiant_hakili__in=identifiants, corpus_reference=False
        )

        supprimees, _ = existantes.delete()
        if options["supprimer"]:
            self.stdout.write(self.style.SUCCESS(f"{supprimees} objet(s) supprimé(s)."))
            return

        for parcours in _PARCOURS:
            self._creer(parcours)

    @transaction.atomic
    def _creer(self, parcours: dict) -> None:
        nom, prenom, contact = parcours["eleve"]
        identifiant = _identifiant(nom, prenom, contact)

        session = Session.objects.create(identifiant_hakili=identifiant)
        evaluation = Evaluation.objects.create(
            session=session,
            type=parcours["type_evaluation"],
            support="démonstration",
        )

        ignores: list[str] = []
        for code_comp, code_type, etat_vise, justification in parcours["problemes"]:
            competence = Competence.objects.filter(pk=code_comp).first()
            type_erreur = TypeErreur.objects.filter(pk=code_type).first()
            if competence is None or type_erreur is None:
                # Un code absent du référentiel est un bug, pas une variante
                # (règle 1 du chantier). On le nomme au lieu de le remplacer par
                # un code voisin : un parcours de démonstration silencieusement
                # amputé ferait croire à un écran incomplet.
                ignores.append(f"{code_comp} × {code_type}")
                continue

            probleme = Probleme.objects.create(
                session=session,
                competence=competence,
                type_erreur=type_erreur,
                cout_estime=cout_precalcule(code_comp, code_type),
                evaluation_origine=evaluation,
                justification=justification,
            )
            self._amener_a(probleme, etat_vise, evaluation)

        # Le palier se calcule, il ne se décrète pas — même en démonstration.
        session.palier = session.calculer_palier()
        session.etat = parcours["etat_session"]
        if session.etat == EtatSession.REMEDIATION:
            from django.utils import timezone

            session.date_inscription = timezone.localdate()
        session.save()

        detail = f"{nom} {prenom} — session {session.pk}, palier {session.palier}, "
        detail += f"{session.problemes.count()} problème(s), {session.cout_total_confirme} h"
        self.stdout.write(self.style.SUCCESS(detail))
        if ignores:
            self.stdout.write(
                self.style.WARNING(
                    "  codes absents du référentiel, ignorés : " + ", ".join(ignores)
                )
            )

    @staticmethod
    def _amener_a(probleme: Probleme, etat_vise: str, evaluation: Evaluation) -> None:
        """Fait passer un problème jusqu'à l'état visé, une transition à la fois.

        `changer_etat()` refuse les sauts : on ne peut pas écrire `en_remediation`
        sur un problème en `hypothese` sans passer par `confirme`. C'est
        exactement ce qu'on veut ici — les transitions intermédiaires sont
        écrites, et l'historique du parcours de démonstration ressemble à un vrai.
        """
        chemin = {
            EtatProbleme.HYPOTHESE: [],
            EtatProbleme.CONFIRME: [EtatProbleme.CONFIRME],
            EtatProbleme.ECARTE: [EtatProbleme.ECARTE],
            EtatProbleme.EN_REMEDIATION: [
                EtatProbleme.CONFIRME,
                EtatProbleme.EN_REMEDIATION,
            ],
        }[etat_vise]

        for etape in chemin:
            probleme.changer_etat(etape, evaluation=evaluation, commentaire="démonstration")
