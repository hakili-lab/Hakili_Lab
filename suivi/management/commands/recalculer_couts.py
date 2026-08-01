"""
Réaligne `Probleme.cout_estime` sur la grille `CoutRemediation` en vigueur.

    python manage.py recalculer_couts --a-blanc
    python manage.py recalculer_couts

Pourquoi cette commande existe
------------------------------
`cout_estime` est **copié** sur le problème au moment où il est créé, pas lu à
la volée. C'est le bon choix — le coût qui a servi à décider d'un palier ne doit
pas changer sous les pieds d'une session déjà inscrite — mais il a une
conséquence : le jour où la formule de coût change, les problèmes déjà en base
gardent l'ancienne échelle, et `Session.cout_total_confirme` continue de
sommer des heures qui n'existent plus dans la grille.

C'est arrivé le 2026-08-01, au passage de l'arrondi à la demi-heure à l'arrondi
à l'heure entière supérieure : les 606 lignes de la grille ont été régénérées à
l'import, les 69 problèmes en base ne l'ont pas été.

Ce que la commande ne fait pas
------------------------------
Elle ne touche **pas** aux sessions déjà inscrites à un programme
(`Session.inscrire()` a figé un palier sur un coût donné) : les réaligner
changerait rétroactivement ce qui a été annoncé à une famille. Elles sont
listées au compte rendu pour être traitées à la main, en connaissance de cause.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from referentiel.couts import cout_precalcule
from suivi.models import Probleme


class Command(BaseCommand):
    help = "Réaligne le coût stocké des problèmes sur la grille de coûts en vigueur."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--a-blanc", action="store_true",
            help="Montre ce qui changerait, sans rien écrire.",
        )

    def handle(self, *args, **options) -> None:
        a_blanc: bool = options["a_blanc"]

        a_corriger: list[tuple[Probleme, object]] = []
        figes: list[Probleme] = []

        for probleme in Probleme.objects.select_related(
            "session", "competence", "type_erreur"
        ).all():
            attendu = cout_precalcule(
                probleme.competence_id, probleme.type_erreur_id
            )
            if attendu == probleme.cout_estime:
                continue
            if getattr(probleme.session, "date_inscription", None):
                figes.append(probleme)
                continue
            a_corriger.append((probleme, attendu))

        if not a_corriger and not figes:
            self.stdout.write(self.style.SUCCESS(
                "Tous les coûts stockés sont déjà alignés sur la grille."
            ))
            return

        for probleme, attendu in a_corriger:
            self.stdout.write(
                f"  {probleme.session.identifiant_hakili:14} "
                f"{probleme.competence_id:10} x {probleme.type_erreur_id}  "
                f"{probleme.cout_estime:g} h -> {attendu:g} h"
            )

        ancien = sum(p.cout_estime for p, _ in a_corriger)
        nouveau = sum(a for _, a in a_corriger)
        self.stdout.write(
            f"\n  {len(a_corriger)} problème(s) à réaligner : "
            f"{ancien:g} h -> {nouveau:g} h ({nouveau - ancien:+g} h)"
        )

        if figes:
            self.stdout.write(self.style.WARNING(
                f"\n  {len(figes)} problème(s) NON touché(s) — leur session est "
                "déjà inscrite à un programme, et son palier a été annoncé sur "
                "l'ancien coût. À reprendre à la main :"
            ))
            for probleme in figes:
                self.stdout.write(
                    f"    {probleme.session.identifiant_hakili:14} "
                    f"{probleme.competence_id} x {probleme.type_erreur_id}"
                )

        if a_blanc:
            self.stdout.write(self.style.WARNING("\n  À blanc — rien n'a été écrit."))
            return

        with transaction.atomic():
            for probleme, attendu in a_corriger:
                probleme.cout_estime = attendu
            Probleme.objects.bulk_update(
                [p for p, _ in a_corriger], ["cout_estime"], batch_size=500
            )

        self.stdout.write(self.style.SUCCESS(
            f"\n  {len(a_corriger)} coût(s) réaligné(s)."
        ))
