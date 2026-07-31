"""
État du corpus de référence — module 3.

**Un instrument de mesure qu'on ne peut pas examiner n'inspire pas confiance.**
Le corpus est l'étalon du module 4 : c'est contre lui que se mesurera l'écart du
diagnostic automatique. Il doit donc pouvoir être relu, compté, et contrôlé.

Trois choses que cette commande donne et qui manquaient :

1. **La composition** — combien de copies, combien de problèmes, comment les
   sept types d'erreur se répartissent. Un corpus qui n'aurait que des `CPT` ne
   mesurerait que la détection de l'effondrement.
2. **La dérive des coûts.** `Probleme.cout_estime` est figé au tagage. Les 27
   volumes horaires du lycée sont aujourd'hui des valeurs de repli (D-CEO-29) :
   le jour où les vrais arrivent, les coûts du corpus resteront faux sans que
   rien ne le signale. `--recalculer` les remet en accord avec le référentiel.
3. **Les hésitations**, relues depuis les fichiers de tagage. C'est la sortie la
   plus précieuse du module 3 — chacune désigne un défaut possible du
   référentiel — et elle ne vivait jusqu'ici que dans des fichiers épars.

Usage :
    python manage.py corpus
    python manage.py corpus --hesitations
    python manage.py corpus --recalculer [--a-blanc]
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from referentiel.couts import cout_precalcule
from suivi.models import Evaluation, Probleme

#: Nombre de copies exigé par le jalon de validation avant que le module 4
#: puisse être mesuré (docs/urie_v2_roadmap.md).
COPIES_ATTENDUES = 5


class Command(BaseCommand):
    help = "État du corpus de référence : composition, dérive des coûts, hésitations."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--recalculer",
            action="store_true",
            help="Remet les coûts estimés en accord avec le référentiel.",
        )
        parser.add_argument(
            "--a-blanc", action="store_true", help="Avec --recalculer : n'écrit rien."
        )
        parser.add_argument(
            "--hesitations",
            action="store_true",
            help="Rassemble les hésitations de tous les fichiers de tagage.",
        )

    def handle(self, *args, **options) -> None:
        if options["hesitations"]:
            self._hesitations()
            return

        evaluations = list(
            Evaluation.objects.filter(corpus_reference=True)
            .select_related("session")
            .order_by("date", "pk")
        )
        if not evaluations:
            self.stdout.write(
                self.style.WARNING(
                    "Le corpus est vide. `manage.py taguer_corpus --fichier …`"
                )
            )
            return

        self._composition(evaluations)
        self._derive(recalculer=options["recalculer"], a_blanc=options["a_blanc"])

    # ── Composition ──────────────────────────────────────────────────────────

    def _composition(self, evaluations: list[Evaluation]) -> None:
        self.stdout.write(self.style.SUCCESS("\n── Copies du corpus ──"))
        total = 0
        for ev in evaluations:
            problemes = list(ev.problemes_reveles.all())
            cout = sum(p.cout_estime for p in problemes)
            total += len(problemes)
            self.stdout.write(
                f"  {ev.session.identifiant_hakili:16} {ev.type}  "
                f"{len(problemes):3} problèmes  {cout:6g} h   "
                f"tagué par {ev.tague_par or '—'} le {ev.date_tagage or '—'}"
            )

        manque = COPIES_ATTENDUES - len(evaluations)
        if manque > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"\n  {len(evaluations)} copie(s) sur {COPIES_ATTENDUES} — il en "
                    f"manque {manque} avant que le module 4 puisse être mesuré."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n  {len(evaluations)} copies — le jalon des {COPIES_ATTENDUES} "
                    f"est atteint."
                )
            )

        problemes = Probleme.objects.filter(evaluation_origine__corpus_reference=True)
        par_type = Counter(problemes.values_list("type_erreur_id", flat=True))
        self.stdout.write(self.style.SUCCESS("\n── Répartition des types d'erreur ──"))
        for code, nombre in sorted(par_type.items(), key=lambda x: -x[1]):
            part = 100 * nombre / max(total, 1)
            self.stdout.write(f"  {code:5} {nombre:4}  {part:5.1f} %  {'█' * int(part / 3)}")

        absents = {"PRQ", "CPT", "MOD", "PRC", "CNS", "RED", "ATT"} - set(par_type)
        if absents:
            self.stdout.write(
                self.style.WARNING(
                    f"\n  Aucun problème de type {', '.join(sorted(absents))} dans le "
                    f"corpus : le module 4 ne pourra pas être mesuré sur ces types."
                )
            )

        doubles = defaultdict(list)
        for p in problemes.select_related():
            doubles[(p.evaluation_origine_id, p.competence_id)].append(p.type_erreur_id)
        multiples = {k: v for k, v in doubles.items() if len(v) > 1}
        if multiples:
            self.stdout.write(
                self.style.WARNING(
                    "\n── Compétences taguées plusieurs fois sur une même copie ──"
                )
            )
            for (ev_id, code), types in sorted(multiples.items()):
                self.stdout.write(
                    f"  évaluation {ev_id} · {code} : {', '.join(sorted(types))} "
                    f"— le coût est compté {len(types)} fois."
                )

    # ── Dérive des coûts ─────────────────────────────────────────────────────

    def _derive(self, *, recalculer: bool, a_blanc: bool) -> None:
        problemes = list(
            Probleme.objects.filter(evaluation_origine__corpus_reference=True)
        )
        ecarts = [
            (p, cout_precalcule(p.competence_id, p.type_erreur_id))
            for p in problemes
        ]
        ecarts = [(p, attendu) for p, attendu in ecarts if p.cout_estime != attendu]

        if not ecarts:
            self.stdout.write(
                self.style.SUCCESS("\n── Coûts : en accord avec le référentiel ──")
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f"\n── Coûts : {len(ecarts)} problème(s) en écart avec le référentiel ──"
            )
        )
        for p, attendu in ecarts:
            self.stdout.write(
                f"  {p.competence_id:12} × {p.type_erreur_id:4} "
                f"figé à {p.cout_estime:g} h, référentiel {attendu:g} h"
            )

        if not recalculer:
            self.stdout.write("  `--recalculer` pour les remettre en accord.")
            return
        if a_blanc:
            self.stdout.write(self.style.WARNING("  À blanc — rien n'a été écrit."))
            return

        with transaction.atomic():
            for p, attendu in ecarts:
                p.cout_estime = attendu
                p.save(update_fields=["cout_estime"])
        self.stdout.write(self.style.SUCCESS(f"  {len(ecarts)} coût(s) recalculé(s)."))

    # ── Hésitations ──────────────────────────────────────────────────────────

    def _hesitations(self) -> None:
        """Relit les fichiers de tagage — les hésitations n'existent qu'en YAML.

        C'est délibéré : une hésitation est un jugement en attente d'arbitrage,
        pas une donnée du suivi. La mettre en base lui donnerait un statut
        qu'elle n'a pas. Mais éparpillée sur cinq fichiers, elle ne remonte à
        personne — d'où ce rassemblement.
        """
        dossier = Path(settings.BASE_DIR) / "data" / "corpus"
        fichiers = sorted(dossier.glob("corpus_*.yaml"))
        if not fichiers:
            self.stdout.write(self.style.WARNING(f"Aucun fichier de tagage dans {dossier}."))
            return

        total = 0
        for chemin in fichiers:
            donnees = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
            hesitations = donnees.get("hesitations") or []
            if not hesitations:
                continue
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n── {chemin.stem} ({donnees.get('identifiant_hakili', '?')}) ──"
                )
            )
            for h in hesitations:
                total += 1
                if isinstance(h, dict):
                    self.stdout.write(f"\n  • {h.get('sur', '?')}")
                    self.stdout.write(f"    {str(h.get('pourquoi', '')).strip()}")
                else:
                    self.stdout.write(f"\n  • {h}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n\n{total} hésitation(s) sur {len(fichiers)} copie(s). "
                f"Chacune désigne un défaut possible du référentiel — à arbitrer "
                f"avec le relecteur pédagogique, pas à corriger seul."
            )
        )
