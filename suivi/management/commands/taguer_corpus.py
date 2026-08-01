"""
Enregistre une copie taguée à la main dans le corpus de référence (module 3).

Le corpus est l'**étalon du module 4** : des copies dont les problèmes ont été
relevés par un humain, contre lesquelles se mesure le diagnostic automatique.
Sans lui, on ne saurait pas si le module 4 fonctionne — seulement qu'il produit
quelque chose. C'est la raison pour laquelle `guide-urie.md` interdit d'automatiser
une tâche avant de l'avoir faite à la main une fois.

Pourquoi un fichier et une commande, plutôt qu'un écran
-------------------------------------------------------
Le tagage est un travail lent et discutable : on relit, on hésite, on corrige. Un
fichier se relit, se compare, se reprend le lendemain ; un formulaire perd tout à
la première fermeture d'onglet. Et chaque problème doit porter sa **justification**
— sans elle, un désaccord entre le corpus et le module 4 serait inarbitrable.

Le trou que la validation ne bouche pas
---------------------------------------
Un code **inventé** est rejeté. Un code **existant mais mal choisi** passe sans
un mot — et pollue l'étalon de façon invisible. Aucun contrôle automatique ne
peut trancher à la place d'un humain ; trois choses réduisent le risque :

· `--chercher` donne le référentiel sous la main, pour ne pas taguer de mémoire ;
· un code rejeté fait proposer les codes les plus proches ;
· le compte rendu **rappelle le libellé** de chaque code retenu, pour qu'une
  relecture rapide fasse ressortir un mauvais choix.

Usage
-----
    python manage.py taguer_corpus --fichier data/corpus/copie_3e.yaml
    python manage.py taguer_corpus --fichier … --a-blanc     # contrôle sans écrire
    python manage.py taguer_corpus --fichier … --remplacer   # refaire un tagage
    python manage.py taguer_corpus --chercher symetrie       # trouver un code
    python manage.py taguer_corpus --chercher --niveau 5eme  # tout un niveau

Format attendu (voir `data/corpus/exemple.yaml`)
-----------------------------------------------
    identifiant_hakili: HK-0042
    tague_par: Prénom Nom
    date_tagage: 2026-07-31
    evaluation:
      type: T0
      date: 2025-11-01
      support: scan 200 DPI — sujet de l'ancien format
      copy_id: ""                      # facultatif
    problemes:
      - competence: N.ENS
        type_erreur: CPT
        etat: hypothese                # ou `confirme`
        justification: ce qu'on lit sur la copie, et pourquoi ce type d'erreur
    hesitations:                       # facultatif mais précieux
      - sur: "question 3b"
        pourquoi: "aucune signature du référentiel ne correspond"
"""
from __future__ import annotations

from pathlib import Path

import yaml
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from difflib import get_close_matches

from django.db import models

from referentiel.couts import cout_precalcule
from referentiel.models import Competence, TypeErreur
from referentiel.niveaux import ORDRE_NIVEAUX
from suivi.models import (
    EtatProbleme,
    Evaluation,
    Probleme,
    Session,
    TypeEvaluation,
)

#: États dans lesquels un tagage manuel peut déposer un problème.
#: Rien d'autre : le corpus décrit ce qu'on a lu sur une copie, pas un parcours
#: de remédiation. Un problème `resolu` dans un corpus n'aurait aucun sens.
ETATS_TAGABLES = {EtatProbleme.HYPOTHESE, EtatProbleme.CONFIRME}

#: Ordre des niveaux — défini une seule fois dans `referentiel/niveaux.py`, le
#: diagnostic sans ancrage (module 4) pose la même question.


class Command(BaseCommand):
    help = "Enregistre une copie taguée à la main dans le corpus de référence (module 3)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--fichier", help="Fichier YAML du tagage.")
        parser.add_argument(
            "--a-blanc",
            action="store_true",
            help="Contrôle tout et n'écrit rien.",
        )
        parser.add_argument(
            "--remplacer",
            action="store_true",
            help="Refait le tagage d'une copie déjà enregistrée : ses problèmes "
            "et leurs transitions sont supprimés puis recréés.",
        )
        parser.add_argument(
            "--chercher",
            nargs="?",
            const="",
            help="Cherche une compétence par mot du libellé ou de la description, "
            "au lieu de taguer. Sans mot, liste tout (à combiner avec --niveau).",
        )
        parser.add_argument(
            "--niveau",
            help="Restreint --chercher à un niveau d'introduction (Primaire, 6eme…).",
        )

    def handle(self, *args, **options) -> None:
        if options.get("chercher") is not None:
            self._chercher(options["chercher"], options.get("niveau"))
            return

        if not options.get("fichier"):
            raise CommandError("--fichier est obligatoire (ou --chercher pour consulter).")
        chemin = Path(options["fichier"])
        if not chemin.exists():
            raise CommandError(f"{chemin} est introuvable.")

        donnees = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
        tagage = self._valider(donnees, chemin)

        if options["a_blanc"]:
            self._rendre_compte(tagage, ecrit=False)
            self.stdout.write(self.style.WARNING("\nÀ blanc — rien n'a été écrit."))
            return

        with transaction.atomic():
            evaluation = self._enregistrer(tagage, remplacer=options["remplacer"])
        self._rendre_compte(tagage, ecrit=True, evaluation=evaluation)

    # ── Consultation ─────────────────────────────────────────────────────────

    def _chercher(self, mot: str, niveau: str | None) -> None:
        """Donne le référentiel sous la main pendant le tagage.

        Sans ça, on tague de mémoire — et on se trompe : le tagage des premières
        copies a conclu à tort qu'aucune compétence ne couvrait le vocabulaire
        géométrique, alors que `G.VOC` existe. Une erreur de ce genre ne se voit
        pas ensuite : le code est valide, il est simplement faux.
        """
        qs = Competence.objects.all()
        if niveau:
            qs = qs.filter(niveau_intro__iexact=niveau)
        if mot:
            qs = qs.filter(
                models.Q(libelle__icontains=mot)
                | models.Q(description__icontains=mot)
                | models.Q(code__icontains=mot)
            )
        qs = qs.order_by("niveau_intro", "code")

        if not qs.exists():
            self.stdout.write(self.style.WARNING("Aucune compétence ne correspond."))
            return

        self.stdout.write(self.style.SUCCESS(f"{qs.count()} compétence(s)\n"))
        for c in qs:
            self.stdout.write(f"  {c.code:12} {c.niveau_intro:10} {c.libelle}")
            if c.description:
                self.stdout.write(f"  {'':12} {'':10} └ {c.description[:100]}")

        self.stdout.write(self.style.SUCCESS("\nTypes d'erreur (liste fermée)"))
        for t in TypeErreur.objects.all():
            self.stdout.write(f"  {t.code:5} {t.libelle}")
            self.stdout.write(f"  {'':5} └ {t.signature[:110]}")

    # ── Validation ───────────────────────────────────────────────────────────

    def _valider(self, donnees: dict, chemin: Path) -> dict:
        """Contrôle tout avant d'écrire quoi que ce soit.

        Le référentiel fait foi : un code de compétence ou de type d'erreur
        absent est **un bug, pas une variante** (protocole-urie.md). Une faute de
        frappe qui passerait ici salirait l'étalon lui-même — et le module 4
        serait ensuite mesuré contre une référence fausse.
        """
        manques = [c for c in ("identifiant_hakili", "tague_par", "date_tagage",
                               "evaluation", "problemes") if not donnees.get(c)]
        if manques:
            raise CommandError(
                f"{chemin.name} : champs obligatoires absents ou vides — "
                f"{', '.join(manques)}."
            )

        evaluation = donnees["evaluation"]
        if not isinstance(evaluation, dict) or not evaluation.get("type"):
            raise CommandError("`evaluation.type` est obligatoire (T0, T1, T3…).")
        if evaluation["type"] not in TypeEvaluation.values:
            raise CommandError(
                f"Type d'évaluation inconnu : {evaluation['type']!r}. "
                f"Attendu parmi {', '.join(TypeEvaluation.values)}."
            )

        problemes = donnees["problemes"]
        if not isinstance(problemes, list):
            raise CommandError("`problemes` doit être une liste.")

        codes_competences = set(Competence.objects.values_list("code", flat=True))
        codes_types = set(TypeErreur.objects.values_list("code", flat=True))
        if not codes_competences:
            raise CommandError(
                "Le référentiel est vide : lancer `manage.py importer_referentiel` "
                "avant de taguer quoi que ce soit."
            )

        erreurs: list[str] = []
        vus: set[tuple[str, str]] = set()
        for rang, item in enumerate(problemes, start=1):
            prefixe = f"problème {rang}"
            if not isinstance(item, dict):
                erreurs.append(f"{prefixe} : ce n'est pas un bloc clé/valeur.")
                continue

            competence = item.get("competence")
            type_erreur = item.get("type_erreur")
            etat = item.get("etat", EtatProbleme.HYPOTHESE)

            if competence not in codes_competences:
                # Proposer les codes proches plutôt que de renvoyer l'utilisateur
                # au classeur : une faute de frappe se corrige en une seconde, et
                # un code cherché de mémoire trouve souvent son voisin ici.
                proches = get_close_matches(str(competence), sorted(codes_competences), n=4, cutoff=0.4)
                indice = f" Peut-être : {', '.join(proches)}." if proches else ""
                erreurs.append(
                    f"{prefixe} : compétence {competence!r} absente du référentiel."
                    f"{indice} (`--chercher <mot>` pour la liste.)"
                )
            if type_erreur not in codes_types:
                erreurs.append(
                    f"{prefixe} : type d'erreur {type_erreur!r} absent du référentiel "
                    f"(liste fermée : {', '.join(sorted(codes_types))})."
                )
            if etat not in ETATS_TAGABLES:
                erreurs.append(
                    f"{prefixe} : état {etat!r} — un tagage manuel dépose une "
                    f"hypothèse ou une confirmation, rien d'autre."
                )
            if not str(item.get("justification", "")).strip():
                erreurs.append(
                    f"{prefixe} : justification vide. Un problème sans justification "
                    f"rend tout désaccord avec le module 4 inarbitrable."
                )
            if type_erreur == "ATT" and etat == EtatProbleme.CONFIRME:
                erreurs.append(
                    f"{prefixe} : ATT (inattention) ne se confirme pas — il existe "
                    f"pour être écarté, et ne donne jamais lieu à remédiation."
                )

            couple = (competence, type_erreur)
            if couple in vus:
                erreurs.append(
                    f"{prefixe} : {competence} × {type_erreur} apparaît deux fois. "
                    f"Un couple ne se suit qu'une fois par session."
                )
            vus.add(couple)

        if erreurs:
            raise CommandError(
                f"{chemin.name} — {len(erreurs)} anomalie(s) :\n  - "
                + "\n  - ".join(erreurs)
            )

        donnees["_avertissements"] = self._avertir(donnees)
        return donnees

    def _avertir(self, donnees: dict) -> list[str]:
        """Signale ce qui est suspect sans être faux. N'empêche jamais d'écrire.

        Deux contrôles, tous deux issus du tagage des premières copies :

        · **Niveau.** Une compétence introduite au niveau du test, ou plus tard,
          n'a pas encore été enseignée — l'échec y est normal et ne devrait pas
          compter comme lacune. Relevé à la main sur une copie d'entrée en 5ème
          taguée `N.FRA2`, compétence de 5ème.
        · **Compétence taguée plusieurs fois.** Deux types d'erreur sur une même
          compétence sont permis et parfois justes, mais ça double le coût :
          autant le voir.
        """
        avertissements: list[str] = []
        niveau = donnees.get("niveau")
        problemes = donnees["problemes"]

        if niveau:
            rang_test = ORDRE_NIVEAUX.get(str(niveau))
            if rang_test is None:
                avertissements.append(
                    f"Niveau {niveau!r} inconnu — contrôle de niveau non effectué. "
                    f"Attendu parmi {', '.join(ORDRE_NIVEAUX)}."
                )
            else:
                niveaux = dict(
                    Competence.objects.filter(
                        code__in=[p["competence"] for p in problemes]
                    ).values_list("code", "niveau_intro")
                )
                for p in problemes:
                    rang = ORDRE_NIVEAUX.get(niveaux.get(p["competence"], ""), -1)
                    if rang >= rang_test:
                        avertissements.append(
                            f"{p['competence']} est introduite en "
                            f"{niveaux[p['competence']]}, or le test est de niveau "
                            f"{niveau} : la compétence n'a pas encore été enseignée, "
                            f"l'échec y est peut-être normal."
                        )

        vus: dict[str, list[str]] = {}
        for p in problemes:
            vus.setdefault(p["competence"], []).append(p["type_erreur"])
        for code, types in vus.items():
            if len(types) > 1:
                avertissements.append(
                    f"{code} est tagué {len(types)} fois ({', '.join(types)}) : "
                    f"légitime si les échecs sont de natures différentes, mais le "
                    f"coût est compté autant de fois."
                )
        return avertissements

    # ── Écriture ─────────────────────────────────────────────────────────────

    def _enregistrer(self, tagage: dict, *, remplacer: bool) -> Evaluation:
        infos = tagage["evaluation"]
        session, creee = Session.objects.get_or_create(
            identifiant_hakili=tagage["identifiant_hakili"],
            defaults={
                "date_debut": infos.get("date") or tagage["date_tagage"],
                "corpus_reference": True,
            },
        )
        # Une session existante qui n'est pas de corpus est le parcours réel d'un
        # élève : y déposer des problèmes d'archive fausserait son coût total,
        # son palier, et ce que sa famille paierait.
        if not creee and not session.corpus_reference:
            raise CommandError(
                f"L'identifiant {session.identifiant_hakili!r} désigne une session "
                f"de suivi réel (créée le {session.date_debut}), pas une session de "
                f"corpus. Taguer une copie d'archive dessus ferait entrer ces "
                f"problèmes dans le palier de cet élève. Employer un identifiant "
                f"de corpus non nominatif (CORPUS-…)."
            )

        existante = Evaluation.objects.filter(
            session=session,
            type=infos["type"],
            date=infos.get("date") or tagage["date_tagage"],
            corpus_reference=True,
        ).first()

        if existante and not remplacer:
            raise CommandError(
                f"Cette copie est déjà dans le corpus (évaluation {existante.pk}, "
                f"{existante.problemes_reveles.count()} problèmes). "
                f"Utiliser --remplacer pour refaire le tagage."
            )

        if existante:
            # Les problèmes du corpus sont une annotation, pas un historique de
            # soin : les refaire est légitime. On ne supprime que ceux que **cette
            # évaluation** a révélés — supprimer tous les problèmes de la session
            # détruirait le suivi réel d'un élève qui en aurait un.
            existante.problemes_reveles.all().delete()
            evaluation = existante
            evaluation.tague_par = tagage["tague_par"]
            evaluation.date_tagage = tagage["date_tagage"]
            evaluation.save(update_fields=["tague_par", "date_tagage"])
        else:
            evaluation = Evaluation.objects.create(
                session=session,
                type=infos["type"],
                date=infos.get("date") or tagage["date_tagage"],
                support=infos.get("support", ""),
                copy_id=infos.get("copy_id", "") or "",
                corpus_reference=True,
                tague_par=tagage["tague_par"],
                date_tagage=tagage["date_tagage"],
            )

        for item in tagage["problemes"]:
            etat = item.get("etat", EtatProbleme.HYPOTHESE)
            probleme = Probleme(
                session=session,
                competence_id=item["competence"],
                type_erreur_id=item["type_erreur"],
                etat=EtatProbleme.HYPOTHESE,
                cout_estime=cout_precalcule(item["competence"], item["type_erreur"]),
                evaluation_origine=evaluation,
                justification=item["justification"].strip(),
            )
            probleme.full_clean()
            probleme.save()

            if etat == EtatProbleme.CONFIRME:
                probleme.changer_etat(
                    EtatProbleme.CONFIRME,
                    evaluation=evaluation,
                    commentaire="Corpus de référence — confirmé au tagage manuel.",
                )

        return evaluation

    # ── Compte rendu ─────────────────────────────────────────────────────────

    def _rendre_compte(self, tagage: dict, *, ecrit: bool, evaluation=None) -> None:
        problemes = tagage["problemes"]
        cout = sum(
            cout_precalcule(p["competence"], p["type_erreur"]) for p in problemes
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{len(problemes)} problème(s) — {cout:g} h de remédiation estimées"
            )
        )

        # Les libellés sont rappelés à dessein. Un code valide mais mal choisi
        # passe toute la validation sans un mot ; relu en toutes lettres, il a
        # une chance de sauter aux yeux — c'est le seul filet contre l'erreur
        # qui compte vraiment, celle qui salit l'étalon sans rien casser.
        libelles = dict(Competence.objects.values_list("code", "libelle"))
        types = dict(TypeErreur.objects.values_list("code", "libelle"))
        for item in problemes:
            etat = item.get("etat", EtatProbleme.HYPOTHESE)
            code, type_erreur = item["competence"], item["type_erreur"]
            unitaire = cout_precalcule(code, type_erreur)
            self.stdout.write(
                f"  {code:12} × {type_erreur:4} [{etat:9}] {unitaire:g} h"
            )
            self.stdout.write(
                f"  {'':12}   └ {libelles.get(code, '?')} × {types.get(type_erreur, '?')}"
            )

        for message in tagage.get("_avertissements", []):
            self.stdout.write(self.style.WARNING(f"\n⚠ {message}"))

        hesitations = tagage.get("hesitations") or []
        if hesitations:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{len(hesitations)} hésitation(s) — à remonter, ce sont des "
                    f"défauts possibles du référentiel, pas des erreurs de tagage :"
                )
            )
            for h in hesitations:
                if isinstance(h, dict):
                    self.stdout.write(f"  · {h.get('sur', '?')} — {h.get('pourquoi', '')}")
                else:
                    self.stdout.write(f"  · {h}")

        if ecrit and evaluation is not None:
            total = Evaluation.objects.filter(corpus_reference=True).count()
            self.stdout.write(
                self.style.SUCCESS(f"\nÉvaluation {evaluation.pk} enregistrée.")
            )
            self.stdout.write(
                f"Corpus de référence : {total} copie(s) sur les 5 attendues "
                f"avant que le module 4 puisse être mesuré."
            )
