"""
Mesure « plancher » du module 4 contre une copie du corpus de référence.

    python manage.py mesurer_plancher --productions data/productions/copie_6e.yaml \
                                      --contre 12

Pourquoi cette commande existe
------------------------------
Le diagnostic contraint travaille **par question** : énoncé, compétence, prérequis
et signatures d'erreur, tous tirés des 280 questions v2. Les 5 copies du corpus
sont de l'**ancien format** et n'en portent aucune — le mode normal ne peut pas
tourner dessus. Tant qu'aucune copie du nouveau format n'existe, le module 4 n'a
rien contre quoi se mesurer.

Cette commande fait tourner le modèle sur la tâche **plus dure** : la production
de l'élève et le catalogue des compétences du niveau, sans aucune signature à
reconnaître. C'est exactement ce qu'a fait l'humain qui a tagué le corpus, donc la
comparaison est loyale — et c'est un **plancher** : le mode ancré, mieux armé, ne
peut que faire aussi bien ou mieux. Un bon résultat ici est encourageant ; il ne
vaut pas le jalon, qui exige la configuration de production.

⚠ Le piège que cette commande refuse de tendre
----------------------------------------------
Il serait tentant d'alimenter la mesure avec `Probleme.justification`, déjà en
base pour les 66 problèmes du corpus. **Ce serait mesurer le vide** : ces
justifications sont écrites par le tagueur et portent le diagnostic en toutes
lettres (« la formule est juste, seul le produit est faux »). Le score serait
excellent et ne voudrait rien dire.

L'entrée est donc un fichier de **productions brutes**, transcrites depuis le
scan, distinct de la base. La commande vérifie que ce fichier ne recopie pas les
justifications du corpus et refuse de tourner si c'est le cas.

Format du fichier de productions
--------------------------------
    identifiant_hakili: CORPUS-6E-05
    niveau_test: 6eme
    productions:
      - repere: "exercice 3b"
        enonce: "Périmètre d'une table circulaire de 1,3 m de diamètre"
        production: "1,3 x 2 = 2,6 m"
"""
from __future__ import annotations

import sys
from difflib import SequenceMatcher
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError

from referentiel.diagnostic import ProductionEleve, diagnostiquer_sans_ancrage
from referentiel.models import NiveauTest
from suivi.mesure import comparer, repartition_par_type
from suivi.models import Evaluation

#: Au-delà de cette ressemblance avec une justification du corpus, une production
#: est considérée comme recopiée depuis l'étalon. 0,75 laisse passer les citations
#: courtes légitimes (« 1,3 x 2 = 2,6 m » figure des deux côtés, c'est normal) et
#: attrape les phrases d'interprétation, qui sont longues et singulières.
SEUIL_RESSEMBLANCE = 0.75

#: En deçà, une production est trop courte pour que la ressemblance ait un sens.
LONGUEUR_MINIMALE_CONTROLE = 60


class Command(BaseCommand):
    help = "Mesure plancher du module 4 contre une copie du corpus de référence."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--productions", required=True,
            help="Fichier YAML des productions brutes de l'élève.",
        )
        parser.add_argument(
            "--contre", type=int, required=True, metavar="ID_EVALUATION",
            help="Évaluation du corpus de référence servant d'étalon.",
        )

    def handle(self, *args, **options) -> None:
        try:
            sys.stdout.reconfigure(errors="replace")
        except (AttributeError, OSError):
            pass

        chemin = Path(options["productions"])
        if not chemin.exists():
            raise CommandError(f"{chemin} est introuvable.")

        etalon_eval = Evaluation.objects.filter(pk=options["contre"]).first()
        if etalon_eval is None:
            raise CommandError(f"Aucune évaluation {options['contre']}.")
        if not etalon_eval.corpus_reference:
            raise CommandError(
                f"L'évaluation {options['contre']} n'appartient pas au corpus de "
                "référence : elle ne fait pas étalon."
            )

        donnees = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
        niveau, productions = self._valider(donnees, chemin)
        self._refuser_la_circularite(productions, etalon_eval)

        client = self._client()
        resultat = diagnostiquer_sans_ancrage(
            niveau_test=niveau,
            productions=productions,
            client=client,
            copy_id=str(donnees.get("identifiant_hakili") or chemin.stem),
        )
        self._rendre_compte(resultat, etalon_eval)

    # ── Entrée ───────────────────────────────────────────────────────────────

    def _valider(self, donnees: dict, chemin: Path) -> tuple[str, list[ProductionEleve]]:
        niveau = donnees.get("niveau_test")
        if niveau not in NiveauTest.values:
            raise CommandError(
                f"`niveau_test` manquant ou inconnu ({niveau!r}). Attendu parmi "
                f"{', '.join(NiveauTest.values)}."
            )

        brutes = donnees.get("productions")
        if not isinstance(brutes, list) or not brutes:
            raise CommandError(f"{chemin.name} : `productions` doit être une liste non vide.")

        productions: list[ProductionEleve] = []
        reperes: set[str] = set()
        for rang, item in enumerate(brutes, start=1):
            if not isinstance(item, dict) or not item.get("repere"):
                raise CommandError(f"production {rang} : `repere` est obligatoire.")
            repere = str(item["repere"]).strip()
            if repere in reperes:
                raise CommandError(
                    f"production {rang} : le repère {repere!r} apparaît deux fois. "
                    "Chaque endroit de la copie doit être identifiable."
                )
            reperes.add(repere)
            productions.append(
                ProductionEleve(
                    repere=repere,
                    enonce=str(item.get("enonce") or "").strip(),
                    production=str(item.get("production") or ""),
                )
            )
        return niveau, productions

    def _refuser_la_circularite(
        self, productions: list[ProductionEleve], etalon: Evaluation
    ) -> None:
        """Refuse un fichier qui recopie les justifications du corpus.

        Sans ce contrôle, la mesure la plus facile à produire serait aussi la
        seule qui ne mesure rien — et elle donnerait le meilleur score. C'est
        exactement le genre de défaut qui survit longtemps : les chiffres sont
        beaux, personne ne les met en doute.
        """
        justifications = [
            j for j in etalon.problemes_reveles.values_list("justification", flat=True) if j
        ]
        if not justifications:
            return

        for production in productions:
            texte = production.production.strip()
            if len(texte) < LONGUEUR_MINIMALE_CONTROLE:
                continue
            for justification in justifications:
                ressemblance = SequenceMatcher(
                    None, texte.lower(), justification.strip().lower()
                ).ratio()
                if ressemblance >= SEUIL_RESSEMBLANCE:
                    raise CommandError(
                        f"Le repère {production.repere!r} reprend à "
                        f"{ressemblance:.0%} une justification du corpus. Ces "
                        f"justifications portent le diagnostic en toutes lettres : "
                        f"les donner en entrée reviendrait à fournir la réponse, "
                        f"et la mesure ne voudrait rien dire. N'entrer que la "
                        f"production brute de l'élève, transcrite du scan."
                    )

    def _client(self):
        from src.api.claude_client import ClaudeClient

        try:
            return ClaudeClient()
        except Exception as exc:  # noqa: BLE001
            # Contrairement à `diagnostiquer`, il n'y a pas de repli utile : sans
            # modèle, la mesure plancher n'a aucune part mécanique à exécuter.
            raise CommandError(
                f"Cette mesure demande un modèle et aucun n'est disponible ({exc}). "
                "Renseigner ANTHROPIC_API_KEY dans .env."
            ) from exc

    # ── Compte rendu ─────────────────────────────────────────────────────────

    def _rendre_compte(self, resultat, etalon_eval: Evaluation) -> None:
        etalon = list(
            etalon_eval.problemes_reveles.values_list("competence_id", "type_erreur_id")
        )
        produit = [(p.code_competence, p.code_type_erreur) for p in resultat.problemes]
        ecart = comparer(etalon, produit)

        self.stdout.write(
            self.style.SUCCESS(
                f"\n── Mesure plancher — copie {resultat.copy_id} contre "
                f"l'évaluation {etalon_eval.pk} du corpus"
            )
        )
        self.stdout.write(
            f"  étalon {ecart.total_etalon} problème(s) · produit {ecart.total_produit}"
        )
        self.stdout.write(
            f"  exacts {len(ecart.exacts)} · compétence juste type faux "
            f"{len(ecart.type_faux)} · manqués {len(ecart.manques)} · en trop "
            f"{len(ecart.en_trop)}"
        )
        self.stdout.write(
            f"  précision {ecart.precision:.0%} · rappel {ecart.rappel:.0%} · "
            f"rappel sur la compétence seule {ecart.rappel_competence:.0%}"
        )
        # Le signe de l'écart n'est pas une nuance : il dit qui paie l'erreur.
        # Une surestimation facture des heures inutiles ; une sous-estimation
        # inscrit un élève sur un volume qui ne suffira pas — et c'est celle-là
        # qu'on ne voit pas venir, parce qu'elle ressemble à un devis raisonnable.
        if ecart.ecart_cout > 0:
            lecture = "surestimation — heures facturées en trop"
        elif ecart.ecart_cout < 0:
            lecture = "SOUS-estimation — le plan promettrait moins d'heures qu'il n'en faut"
        else:
            lecture = "exact"
        self.stdout.write(
            f"  coût : étalon {ecart.cout_etalon:g} h, produit "
            f"{ecart.cout_produit:g} h, écart {ecart.ecart_cout:+g} h ({lecture})"
        )

        if ecart.type_faux:
            self.stdout.write(
                self.style.WARNING(
                    "\n  Compétence trouvée, type d'erreur différent — c'est ce qui "
                    "envoie le tuteur travailler la mauvaise chose :"
                )
            )
            for competence, attendu, obtenu in ecart.type_faux:
                self.stdout.write(
                    f"    {competence:12} corpus {attendu} ≠ module 4 {obtenu}"
                )

        for titre, couples in (
            ("Manqués (lacune non vue)", ecart.manques),
            ("En trop (lacune inventée)", ecart.en_trop),
        ):
            if couples:
                self.stdout.write(self.style.WARNING(f"\n  {titre} :"))
                for competence, type_erreur in couples:
                    self.stdout.write(f"    {competence:12} × {type_erreur}")

        self.stdout.write(f"\n  répartition étalon   : {repartition_par_type(etalon)}")
        self.stdout.write(f"  répartition module 4 : {repartition_par_type(produit)}")

        if resultat.rejets:
            self.stdout.write(
                self.style.ERROR(
                    f"\n  {len(resultat.rejets)} sortie(s) refusée(s) après redemande :"
                )
            )
            for motif in resultat.rejets:
                self.stdout.write(f"    · {motif}")

        self.stdout.write(
            self.style.WARNING(
                "\n⚠ Mesure plancher : le modèle a travaillé **sans les signatures "
                "d'erreur** du référentiel, sur une copie de l'ancien format. Elle "
                "n'atteste pas le jalon du module 4, qui exige la configuration de "
                "production sur des copies du nouveau format."
            )
        )
