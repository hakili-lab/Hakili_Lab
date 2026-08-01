"""
Importe `Referentiel_Urie_v0.xlsx` en base — commande idempotente.

    python manage.py importer_referentiel
    python manage.py importer_referentiel --classeur /chemin/Referentiel.xlsx
    python manage.py importer_referentiel --a-blanc     # rapport sans écriture

Import strict, par choix
------------------------
Un code de compétence ou de type d'erreur absent du référentiel fait **échouer**
l'import au lieu d'être ignoré. L'intégrité du classeur a été vérifiée (module 0 :
zéro violation sur 280 questions, 1031 signatures et 284 options), donc une
violation signalerait une vraie régression du classeur, pas un cas limite à
absorber en silence.

Deux stratégies d'écriture, et pourquoi
---------------------------------------
- `TypeErreur`, `Competence`, `Question` sont **mises à jour**, jamais supprimées :
  le suivi des élèves pointe dessus (`Probleme`, `Reponse`). Les supprimer pour les
  recréer perdrait ces liens.
- `Prerequis`, `CoutRemediation`, `SignatureErreur`, `OptionQcm` sont **remplacées
  en bloc** : rien ne pointe vers elles, et un remplacement garantit qu'une ligne
  retirée du classeur disparaît vraiment de la base — ce qu'une simple mise à jour
  laisserait traîner.

Barème
------
Le classeur note sur 60, les sujets sur 20 (décision D-CEO-26). La conversion se
fait ici, à l'import, en divisant par 3. `bareme_classeur` conserve la valeur
d'origine, entière donc exacte.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from referentiel.models import (
    Competence,
    CoutRemediation,
    OptionQcm,
    Prerequis,
    Question,
    SignatureErreur,
    TypeErreur,
)

# Le classeur vit au-dessus du dépôt, dans le dossier de travail.
_CANDIDATS = [
    Path(__file__).resolve().parents[4].parent / "Referentiel_Urie_v0.xlsx",
    Path(__file__).resolve().parents[4] / "Referentiel_Urie_v0.xlsx",
]

_DIVISEUR_BAREME = Decimal(3)


def _texte(valeur) -> str:
    return "" if valeur is None else str(valeur).strip()


def _oui(valeur) -> bool:
    return _texte(valeur).upper() in {"OUI", "YES", "TRUE", "1"}


def _decimal(valeur) -> Decimal | None:
    """Retourne None sur « non disponible » — le cas des 27 compétences de lycée,
    dont les documents officiels ne donnent pas le volume par chapitre."""
    brut = _texte(valeur)
    if not brut or brut.lower().startswith("non disponible"):
        return None
    try:
        return Decimal(brut.replace(",", "."))
    except Exception:
        return None


class Command(BaseCommand):
    help = "Importe le référentiel Urie (compétences, types d'erreur, questions, coûts)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--classeur", type=str, default="", help="Chemin du .xlsx")
        parser.add_argument(
            "--a-blanc",
            action="store_true",
            help="Analyse et rapporte sans rien écrire en base.",
        )

    def handle(self, *args, **options) -> None:
        chemin = self._resoudre_classeur(options["classeur"])
        self.stdout.write(f"Classeur : {chemin}\n")

        wb = openpyxl.load_workbook(chemin, data_only=True, read_only=True)
        try:
            onglets = {
                nom: list(wb[nom].iter_rows(values_only=True))[1:]
                for nom in (
                    "01_Types_erreur",
                    "02_Competences",
                    "04_Questions",
                    "05_Grille_diagnostic",
                    "06_Distracteurs",
                    "08_Cout_remediation",
                )
            }
        except KeyError as exc:
            raise CommandError(f"Onglet manquant dans le classeur : {exc}") from exc
        finally:
            wb.close()

        self._verifier_integrite(onglets)

        if options["a_blanc"]:
            self.stdout.write(
                self.style.WARNING("\n  Marche à blanc — aucune écriture en base.")
            )
            for nom, lignes in onglets.items():
                self.stdout.write(f"    {nom:24s} {len(lignes):5d} lignes lues")
            return

        with transaction.atomic():
            n_types = self._importer_types_erreur(onglets["01_Types_erreur"])
            n_comp, n_prereq = self._importer_competences(onglets["02_Competences"])
            n_couts, n_estimes = self._importer_couts(onglets["08_Cout_remediation"])
            n_quest = self._importer_questions(onglets["04_Questions"])
            n_sign = self._importer_signatures(onglets["05_Grille_diagnostic"])
            n_opts, n_rep = self._importer_options(onglets["06_Distracteurs"])

        self.stdout.write("")
        for libelle, n in [
            ("Types d'erreur", n_types),
            ("Compétences", n_comp),
            ("Liens de prérequis", n_prereq),
            ("Coûts de remédiation", n_couts),
            ("  dont estimés (lycée)", n_estimes),
            ("Questions", n_quest),
            ("Signatures d'erreur", n_sign),
            ("Options de QCM", n_opts),
        ]:
            self.stdout.write(f"  {libelle:24s} {n:5d}")

        sans_corrige = Question.objects.filter(reponse_attendue="").count()
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"  Import terminé. {n_rep} QCM avec bonne réponse.")
        )
        if sans_corrige:
            self.stdout.write(
                self.style.WARNING(
                    f"  {sans_corrige} questions sans corrigé — le classeur n'en "
                    "contient pas pour les formats autres que QCM (arbitrage B de "
                    "docs/harmonisation_donnees.md)."
                )
            )

    # ── Résolution du fichier ────────────────────────────────────────────────

    def _resoudre_classeur(self, fourni: str) -> Path:
        if fourni:
            chemin = Path(fourni).expanduser().resolve()
            if not chemin.exists():
                raise CommandError(f"Classeur introuvable : {chemin}")
            return chemin
        for candidat in _CANDIDATS:
            if candidat.exists():
                return candidat
        raise CommandError(
            "Referentiel_Urie_v0.xlsx introuvable. Cherché dans :\n  "
            + "\n  ".join(str(c) for c in _CANDIDATS)
            + "\nPréciser le chemin avec --classeur."
        )

    # ── Contrôle préalable ───────────────────────────────────────────────────

    def _verifier_integrite(self, onglets: dict) -> None:
        """Échoue avant toute écriture si un code est inconnu.

        Contrôler d'abord évite d'écrire la moitié du référentiel puis d'échouer :
        la transaction annulerait bien l'écriture, mais le message serait obscur.
        """
        codes_types = {_texte(r[0]) for r in onglets["01_Types_erreur"] if _texte(r[0])}
        codes_comp = {_texte(r[0]) for r in onglets["02_Competences"] if _texte(r[0])}
        erreurs: list[str] = []

        for ligne in onglets["04_Questions"]:
            for col, role in ((6, "principale"), (7, "secondaire")):
                code = _texte(ligne[col])
                if code and code not in codes_comp:
                    erreurs.append(
                        f"04_Questions {_texte(ligne[0])}/{_texte(ligne[1])} : "
                        f"compétence {role} « {code} » inconnue"
                    )

        for ligne in onglets["05_Grille_diagnostic"]:
            if (code := _texte(ligne[2])) and code not in codes_comp:
                erreurs.append(f"05_Grille_diagnostic : compétence « {code} » inconnue")
            if (code := _texte(ligne[3])) and code not in codes_types:
                erreurs.append(f"05_Grille_diagnostic : type d'erreur « {code} » inconnu")

        for ligne in onglets["06_Distracteurs"]:
            if (code := _texte(ligne[5])) and code not in codes_types:
                erreurs.append(f"06_Distracteurs : type d'erreur « {code} » inconnu")

        for ligne in onglets["08_Cout_remediation"]:
            if (code := _texte(ligne[0])) and code not in codes_comp:
                erreurs.append(f"08_Cout_remediation : compétence « {code} » inconnue")
            if (code := _texte(ligne[3])) and code not in codes_types:
                erreurs.append(f"08_Cout_remediation : type d'erreur « {code} » inconnu")

        if erreurs:
            apercu = "\n  ".join(erreurs[:15])
            reste = f"\n  … et {len(erreurs) - 15} autres" if len(erreurs) > 15 else ""
            raise CommandError(
                f"{len(erreurs)} référence(s) inconnue(s) dans le classeur :\n  "
                f"{apercu}{reste}\n\nAucune écriture effectuée."
            )

    # ── Référentiel ──────────────────────────────────────────────────────────

    def _importer_types_erreur(self, lignes: list) -> int:
        n = 0
        for r in lignes:
            code = _texte(r[0])
            if not code:
                continue
            TypeErreur.objects.update_or_create(
                code=code,
                defaults={
                    "libelle": _texte(r[1]),
                    "definition": _texte(r[2]),
                    "signature": _texte(r[3]),
                    "exemple": _texte(r[4]),
                    "coefficient": _decimal(r[5]) or Decimal(0),
                    "remediable": _oui(r[6]),
                },
            )
            n += 1
        return n

    def _importer_competences(self, lignes: list) -> tuple[int, int]:
        from referentiel.couts import VOLUME_REPLI_LYCEE

        n = 0
        liens: list[tuple[str, str]] = []
        for r in lignes:
            code = _texte(r[0])
            if not code:
                continue

            volume = _decimal(r[8])
            estime = volume is None
            if estime:
                # Sans volume, aucun coût n'est calculable et le palier de l'élève
                # reste indéterminable. On applique la valeur de repli — marquée
                # comme telle, jamais confondue avec un chiffre officiel.
                volume = VOLUME_REPLI_LYCEE

            Competence.objects.update_or_create(
                code=code,
                defaults={
                    "domaine": _texte(r[1]),
                    "libelle": _texte(r[2]),
                    "description": _texte(r[3]),
                    "niveau_intro": _texte(r[4]),
                    "chapitre_intro": _texte(r[5]),
                    "transversale": _oui(r[6]),
                    "volume_horaire": volume,
                    "source_volume": _texte(r[9]),
                    "volume_estime": estime,
                },
            )
            n += 1
            # Les prérequis multiples sont séparés par « ; » dans le classeur.
            for prereq in (p.strip() for p in _texte(r[7]).split(";")):
                if prereq:
                    liens.append((code, prereq))

        connus = set(Competence.objects.values_list("code", flat=True))
        inconnus = {p for _, p in liens if p not in connus}
        if inconnus:
            raise CommandError(
                f"Prérequis pointant vers des compétences inexistantes : "
                f"{sorted(inconnus)}"
            )

        Prerequis.objects.all().delete()
        Prerequis.objects.bulk_create(
            [
                Prerequis(competence_id=c, prerequis_id=p)
                for c, p in liens
                if c != p  # une compétence prérequis d'elle-même bouclerait
            ]
        )
        return n, Prerequis.objects.count()

    def _importer_couts(self, lignes: list) -> tuple[int, int]:
        """Coûts du classeur, complétés pour les compétences sans volume officiel.

        Le classeur ne contient que les 444 coûts des 74 compétences chiffrées. Les
        27 du lycée n'y figurent pas — sans elles, le palier d'un élève de 2nde ou
        de 1ère est indéterminable. On calcule donc leurs coûts depuis le volume de
        repli, avec la formule du protocole, et on les marque `estime`.
        """
        from referentiel.couts import arrondir_heures, cout_remediation

        CoutRemediation.objects.all().delete()

        # Le coût du classeur passe par `arrondir_heures` comme celui du repli :
        # le classeur arrondit à la demi-heure, la règle du dispositif est
        # l'heure entière supérieure. Sans ce passage, les 444 coûts officiels
        # — 73 % de la grille — garderaient leurs demi-heures.
        objets = [
            CoutRemediation(
                competence_id=_texte(r[0]),
                type_erreur_id=_texte(r[3]),
                cout_heures=arrondir_heures(_decimal(r[6]) or Decimal("0.5")),
                derivation=_texte(r[7]),
                estime=False,
            )
            for r in lignes
            if _texte(r[0]) and _texte(r[3])
        ]
        officiels = len(objets)

        # Compétences que le classeur ne chiffre pas × types remédiables.
        deja = {(o.competence_id, o.type_erreur_id) for o in objets}
        remediables = list(TypeErreur.objects.filter(coefficient__gt=0))
        for competence in Competence.objects.filter(volume_estime=True):
            for type_erreur in remediables:
                if (competence.code, type_erreur.code) in deja:
                    continue
                objets.append(
                    CoutRemediation(
                        competence_id=competence.code,
                        type_erreur_id=type_erreur.code,
                        cout_heures=cout_remediation(
                            competence.volume_horaire, type_erreur.coefficient
                        ),
                        derivation=(
                            f"estimation : {competence.volume_horaire:g} h "
                            f"(repli) x {type_erreur.coefficient}"
                        ),
                        estime=True,
                    )
                )

        CoutRemediation.objects.bulk_create(objets, batch_size=500)
        return officiels, len(objets) - officiels

    # ── Banque de questions ──────────────────────────────────────────────────

    def _importer_questions(self, lignes: list) -> int:
        n = 0
        for r in lignes:
            niveau, code = _texte(r[0]), _texte(r[1])
            if not (niveau and code):
                continue
            bareme_classeur = _decimal(r[3]) or Decimal(0)
            secondaire = _texte(r[7]) or None
            Question.objects.update_or_create(
                niveau_test=niveau,
                code_question=code,
                defaults={
                    "partie": _texte(r[2]),
                    "format": _texte(r[4]),
                    "bareme": bareme_classeur / _DIVISEUR_BAREME,
                    "bareme_classeur": bareme_classeur,
                    "code_local": _texte(r[5]),
                    "competence_id": _texte(r[6]),
                    "competence_secondaire_id": secondaire,
                    "objet": _texte(r[8]),
                },
            )
            n += 1
        return n

    def _importer_signatures(self, lignes: list) -> int:
        SignatureErreur.objects.all().delete()
        index = {
            (q.niveau_test, q.code_question): q.pk
            for q in Question.objects.only("pk", "niveau_test", "code_question")
        }
        objets = []
        orphelines: list[str] = []
        for r in lignes:
            cle = (_texte(r[0]), _texte(r[1]))
            if cle not in index:
                orphelines.append(f"{cle[0]}/{cle[1]}")
                continue
            objets.append(
                SignatureErreur(
                    question_id=index[cle],
                    competence_id=_texte(r[2]),
                    type_erreur_id=_texte(r[3]),
                    production_eleve=_texte(r[4]),
                    interpretation=_texte(r[5]),
                )
            )
        if orphelines:
            raise CommandError(
                f"{len(orphelines)} signature(s) rattachée(s) à une question "
                f"inexistante : {sorted(set(orphelines))[:10]}"
            )
        SignatureErreur.objects.bulk_create(objets, batch_size=500)
        return len(objets)

    def _importer_options(self, lignes: list) -> tuple[int, int]:
        """Écrit les options ET remplit `Question.reponse_attendue` pour les QCM.

        C'est ce qui rend un QCM corrigeable et diagnosticable sans aucun appel de
        modèle : la lettre cochée suffit.
        """
        OptionQcm.objects.all().delete()
        index = {
            (q.niveau_test, q.code_question): q
            for q in Question.objects.only("pk", "niveau_test", "code_question")
        }

        objets: list[OptionQcm] = []
        bonnes: dict[Question, list[str]] = {}
        for r in lignes:
            cle = (_texte(r[0]), _texte(r[1]))
            question = index.get(cle)
            if question is None:
                raise CommandError(
                    f"06_Distracteurs : option rattachée à une question inexistante {cle}"
                )
            correcte = _oui(r[4])
            objets.append(
                OptionQcm(
                    question_id=question.pk,
                    lettre=_texte(r[2]),
                    texte=_texte(r[3]),
                    correcte=correcte,
                    # La contrainte `option_type_erreur_coherent` impose qu'une
                    # bonne réponse ne porte pas de type d'erreur.
                    type_erreur_id=None if correcte else (_texte(r[5]) or None),
                    erreur="" if correcte else _texte(r[6]),
                )
            )
            if correcte:
                bonnes.setdefault(question, []).append(_texte(r[2]))

        OptionQcm.objects.bulk_create(objets, batch_size=500)

        ambigues = [q for q, lettres in bonnes.items() if len(lettres) != 1]
        if ambigues:
            raise CommandError(
                f"{len(ambigues)} QCM sans bonne réponse unique — un QCM doit en "
                f"avoir exactement une pour être corrigeable sans interprétation : "
                f"{[str(q) for q in ambigues[:10]]}"
            )

        for question, lettres in bonnes.items():
            question.reponse_attendue = lettres[0]
        Question.objects.bulk_update(bonnes, ["reponse_attendue"], batch_size=500)

        return len(objets), len(bonnes)
