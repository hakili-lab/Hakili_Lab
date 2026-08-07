"""
Diagnostic contraint — module 4 du chantier v2.

Ce que ça remplace
------------------
`DiagnosticResult` produit de la prose : « l'élève a des difficultés en calcul
littéral ». Ça ne se compte pas, ça ne se compare pas d'une passation à l'autre,
et ça ne se chiffre pas. Ici, la sortie est une liste de **problèmes** —
compétence × type d'erreur — c'est-à-dire des lignes de la table `probleme`, avec
un coût, un cycle de vie et une date. C'est ce qui rend une progression mesurable.

Les trois barrières contre un code inventé
------------------------------------------
Le protocole est catégorique : « aucun code de compétence ou de type d'erreur
n'est inventé, un code absent est un bug, pas une variante ». Trois mécanismes
indépendants, parce qu'aucun ne suffit seul :

1. **Le schéma de l'outil** (`src/api/claude_client.py`) déclare les codes en
   `enum`. Un code hors référentiel devient très difficile à produire.
2. **La validation par question**, ici. L'`enum` ne peut porter qu'une liste pour
   tout le tableau ; il n'empêche donc pas d'attribuer à la question `L5` une
   compétence admissible pour `G13`. Cette vérification-là est par question.
3. **La redemande.** Une sortie refusée n'est pas réparée à la place du modèle :
   on lui dit ce qui n'allait pas et on redemande une fois. Ce qui reste invalide
   est **écarté**, jamais corrigé au jugé — un problème inventé oriente une
   remédiation vers la mauvaise notion, une absence se rattrape.

Les QCM ne passent jamais par le modèle
---------------------------------------
Une lettre cochée donne le type d'erreur directement par `option_qcm`, et la
contrainte `option_type_erreur_coherent` garantit en base que toute mauvaise
option en porte un. Appeler un modèle de langage là-dessus coûterait de l'argent
pour introduire une incertitude là où il n'y en a aucune (guide-v2.md, module 4).

Ce qui n'est pas diagnostiqué est dit
-------------------------------------
`questions_ecartees` est aussi importante que `problemes`. Une question écartée —
format `construction`, réponse illisible, absence de client — n'a été jugée par
personne. Sans la nommer, son absence de problème se lirait comme une réussite,
et l'élève passerait pour meilleur qu'il n'est.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from referentiel.contexte import PROFONDEUR_PREREQUIS, chaine_prerequis
from referentiel.models import Competence, FormatQuestion, Question, TypeErreur
from referentiel.niveaux import deja_enseigne
from src.models.domain import (
    CopyGrade,
    DiagnosticContraint,
    ProblemeDetecte,
    Rubric,
    SortieDiagnosticContraint,
    SourceProbleme,
    TeacherDecision,
)

logger = logging.getLogger(__name__)

#: Une seule redemande. Au-delà, le modèle ne comprend pas la contrainte et
#: insister coûte un appel pour la même sortie.
REDEMANDES_MAX = 1

#: Texte de citation d'une zone restée vierge. Constante plutôt que littéral :
#: la mesure contre le corpus s'en sert pour reconnaître ce cas.
CITATION_VIDE = "(aucune réponse)"

#: Une réponse de QCM : la lettre seule, éventuellement ponctuée — « b », « (b) ».
_LETTRE_SEULE = re.compile(r"^[^\w]*([A-Za-z])[\s).:\-]*$")
#: Ou la lettre suivie d'un marqueur de choix, quand l'élève recopie l'option :
#: « b) 4x² + 9 ». Sans marqueur, on n'interprète pas — « b et c » reste ambigu.
_LETTRE_MARQUEE = re.compile(r"^[^\w]*([A-Za-z])[).:]")


@dataclass(frozen=True)
class ReponseEleve:
    """Ce qu'on a lu sur la copie pour une question.

    Volontairement détachée du modèle Django `Reponse` : une copie de l'ancien
    format n'a pas de `Reponse` enregistrable du tout (elle n'a aucune des 280
    questions v2). Le moteur travaille donc sur une entrée simple, et
    l'écriture en base est une étape séparée (`suivi/diagnostic.py`).

    En production, ces objets viennent de la correction déjà faite —
    `reponses_depuis_correction()` ci-dessous. Ils peuvent aussi être écrits à la
    main dans un fichier YAML (`manage.py diagnostiquer --fichier`), ce qui sert
    aux essais et au rejeu.
    """

    code_question: str
    contenu: str = ""
    #: L'élève n'a rien écrit. Distinct d'un contenu vide côté outillage : une
    #: lecture ratée n'est pas une absence de réponse, et les deux ne se
    #: diagnostiquent pas pareil — une zone vierge est un signal, une lecture
    #: ratée est un trou.
    vide: bool = False
    #: Quelque chose est écrit mais n'a pas pu être lu. Ni diagnosticable ni
    #: assimilable à une absence : la question part en écartée, sous un motif qui
    #: dit à l'enseignant qu'il y a là une réponse à relire.
    illisible: bool = False
    #: `True` = question réussie, à ne pas diagnostiquer. `None` = non corrigée,
    #: on diagnostique — l'appelant décide s'il filtre en amont.
    correcte: bool | None = None


#: Ce que la correction écrit dans `observed_answer` quand l'élève n'a rien
#: écrit (`prompts/grading_prompt.md`, étape 1). Constante plutôt que littéral :
#: c'est un contrat entre deux étapes, pas un détail de formatage.
MARQUEUR_ABSENCE = "—"
#: Et ce qu'elle écrit quand il y a une réponse mais qu'elle ne se lit pas.
MARQUEUR_ILLISIBLE = "[ILLISIBLE]"


def reponses_depuis_correction(grade: CopyGrade, rubric: Rubric) -> list[ReponseEleve]:
    """Les réponses de l'élève, telles que la correction les a déjà relevées.

    **C'est le seul chemin d'entrée du diagnostic en production, et il ne coûte
    rien.** La correction lit la copie page entière et rend, pour chaque question
    du barème, ce que l'élève a écrit (`observed_answer`) et si c'est juste. Or
    l'identifiant d'item du barème **est** le code de question du référentiel
    (`D1`, `L5`…) : la correspondance est directe, sans géométrie, sans découpe,
    et sans un seul appel de modèle supplémentaire.

    C'est ce qui a permis de retirer le module 2. Il découpait la copie en une
    image par question pour reconstituer cette même correspondance à partir de la
    position des cadres sur le scan — donc en exigeant une impression sans
    réduction, un scan droit, et le bon nombre de pages dans le bon ordre. Le code
    de la question est imprimé dans son cadre, à côté de la réponse : le lire est
    plus robuste que le déduire d'une géométrie qu'on ne maîtrise pas.

    Deux règles de conversion valent d'être dites :

    - **Les questions réussies ne sont pas soumises** (`correcte=True`). Le
      diagnostic cherche des lacunes ; une réussite n'en porte pas.
    - **La décision de l'enseignant prime sur la proposition de l'IA** pour
      décider ce qui est réussi — c'est la règle du projet sur le score, elle
      vaut tout autant ici : diagnostiquer une question que l'enseignant vient de
      valider produirait une lacune que personne ne constate.
    """
    maxima = {item.id: item.max_score for item in rubric.items}
    reponses: list[ReponseEleve] = []

    for question in grade.questions:
        if question.teacher_decision == TeacherDecision.refused and question.teacher_score is not None:
            score = question.teacher_score
        else:
            score = question.score

        maximum = maxima.get(question.rubric_item_id)
        # Sans maximum connu, on ne peut pas dire qu'une question est réussie :
        # `None` fait diagnostiquer, ce qui est le sens sûr de l'incertitude.
        correcte = None if maximum is None else score >= maximum

        contenu = (question.observed_answer or "").strip()
        reponses.append(
            ReponseEleve(
                code_question=question.rubric_item_id,
                contenu=contenu,
                vide=contenu in ("", MARQUEUR_ABSENCE),
                illisible=MARQUEUR_ILLISIBLE in contenu,
                correcte=correcte,
            )
        )

    return reponses


@dataclass
class _Lot:
    """Ce qui part au modèle, et ce qui a déjà été tranché sans lui."""

    charge: list[dict] = field(default_factory=list)
    admis_par_question: dict[str, set[str]] = field(default_factory=dict)
    problemes: list[ProblemeDetecte] = field(default_factory=list)
    ecartees: dict[str, str] = field(default_factory=dict)
    traitees: list[str] = field(default_factory=list)


# ── Codes admissibles ────────────────────────────────────────────────────────


def codes_competence_admis(question: Question) -> list[str]:
    """Compétences qu'un problème sur cette question peut légitimement viser.

    La compétence évaluée, sa secondaire s'il y en a une, et la **chaîne de
    prérequis** : c'est `PRQ` qui impose d'ouvrir au-delà de la question. Ce type
    d'erreur signifie précisément que la lacune est en amont — « l'élève ne rate
    pas les identités remarquables, il ne sait pas additionner deux relatifs ».
    Restreindre à la seule compétence de la question rendrait `PRQ` inexprimable.

    Ordre : la compétence de la question d'abord, ses prérequis ensuite du plus
    proche au plus lointain. La liste est lue par un humain dans le prompt.
    """
    codes = [question.competence_id]
    if question.competence_secondaire_id:
        codes.append(question.competence_secondaire_id)
    for requis in chaine_prerequis(question.competence, PROFONDEUR_PREREQUIS):
        if requis.code not in codes:
            codes.append(requis.code)
    return codes


# ── QCM : aucun appel de modèle ──────────────────────────────────────────────


def lettre_cochee(contenu: str, lettres_possibles: set[str]) -> str | None:
    """Lettre choisie par l'élève, ou `None` si la réponse ne se lit pas.

    Ne devine jamais. « b et c » ne donne pas `b` : l'élève a coché deux options,
    ce qui n'est pas une réponse valide au QCM et relève du jugement d'un humain.
    Le projet s'est déjà donné cette règle sur les accents et sur l'appariement
    des copies — une donnée devinée est pire qu'une donnée manquante.
    """
    texte = (contenu or "").strip()
    if not texte:
        return None
    for motif in (_LETTRE_SEULE, _LETTRE_MARQUEE):
        trouve = motif.match(texte)
        if trouve:
            lettre = trouve.group(1).lower()
            if lettre in lettres_possibles:
                return lettre
            return None
    return None


def diagnostiquer_qcm(
    question: Question, reponse: ReponseEleve
) -> tuple[ProblemeDetecte | None, str]:
    """Diagnostic mécanique d'un QCM. Rend (problème, motif d'écart).

    Une seule des deux valeurs est renseignée. Une bonne réponse ne donne ni
    problème ni motif : il n'y a rien à signaler.
    """
    options = {o.lettre.lower(): o for o in question.options.all()}
    if not options:
        return None, (
            "QCM sans options au référentiel — l'import du classeur est incomplet."
        )

    if reponse.vide or not (reponse.contenu or "").strip():
        # Une case non cochée n'est pas une erreur de raisonnement identifiable :
        # aucune option ne la décrit, donc aucun type d'erreur ne s'en déduit.
        # C'est un cas fréquent et il doit rester visible plutôt que d'être
        # rattaché au hasard à `CNS`.
        return None, "aucune option cochée — à trancher par l'enseignant"

    lettre = lettre_cochee(reponse.contenu, set(options))
    if lettre is None:
        return None, (
            f"réponse « {reponse.contenu.strip()[:40]} » non interprétable comme "
            f"une option ({', '.join(sorted(options))})"
        )

    option = options[lettre]
    if option.correcte:
        return None, ""

    return (
        ProblemeDetecte(
            code_question=question.code_question,
            code_competence=question.competence_id,
            code_type_erreur=option.type_erreur_id,
            citation=f"option {option.lettre} cochée — {option.texte}".strip(),
            source=SourceProbleme.qcm,
        ),
        "",
    )


# ── Préparation du lot envoyé au modèle ──────────────────────────────────────


def _charge_utile(question: Question, reponse: ReponseEleve, admis: list[str]) -> dict:
    """Ce que le modèle reçoit pour une question.

    Les **signatures** sont le cœur : elles disent ce qu'un élève écrit quand il
    échoue et la lacune que ça révèle. C'est ce qui transforme la tâche de
    « deviner un type d'erreur » en « reconnaître une signature ». 1 031 signatures
    couvrent les 280 questions, 3 à 4 chacune (vérifié au module 0).
    """
    competence = question.competence
    return {
        "code_question": question.code_question,
        "partie": question.partie,
        "format": question.format,
        "enonce": question.objet,
        "competence_evaluee": {
            "code": competence.code,
            "libelle": competence.libelle,
            "description": competence.description or "",
            "introduite_en": competence.niveau_intro,
        },
        "codes_competence_admis": admis,
        # Vide pour 209 des 280 questions (arbitrage B en attente). Le champ est
        # envoyé quand même : son absence est une information pour le modèle, qui
        # doit alors juger sur la seule cohérence de la production.
        "reponse_attendue": question.reponse_attendue or "",
        "demarche_attendue": question.solution or "",
        "reponse_eleve": (
            CITATION_VIDE if reponse.vide or not reponse.contenu.strip()
            else reponse.contenu.strip()
        ),
        "zone_vierge": bool(reponse.vide or not reponse.contenu.strip()),
        "signatures_erreur": [
            {
                "type_erreur": s.type_erreur_id,
                "production_eleve": s.production_eleve,
                "lacune_revelee": s.interpretation,
            }
            for s in question.signatures.all()
        ],
    }


def preparer(niveau_test: str, reponses: list[ReponseEleve]) -> _Lot:
    """Trie les réponses : tranchées mécaniquement, à soumettre, ou écartées."""
    lot = _Lot()

    a_diagnostiquer = [r for r in reponses if r.correcte is not True]
    codes = [r.code_question for r in a_diagnostiquer]
    questions = {
        q.code_question: q
        for q in Question.objects.filter(
            niveau_test=niveau_test, code_question__in=codes
        )
        .select_related("competence", "competence_secondaire")
        .prefetch_related("signatures", "options")
    }

    for reponse in a_diagnostiquer:
        question = questions.get(reponse.code_question)
        if question is None:
            lot.ecartees[reponse.code_question] = (
                f"question absente du référentiel pour le niveau {niveau_test}"
            )
            continue

        if reponse.illisible:
            # Il y a une réponse, elle n'a pas été lue. La soumettre reviendrait à
            # faire diagnostiquer « [ILLISIBLE] », dont le modèle ne peut rien
            # tirer d'autre qu'une invention. L'enseignant, lui, a la copie.
            lot.ecartees[reponse.code_question] = (
                "réponse non déchiffrée à la lecture — à relire sur la copie"
            )
            continue

        if question.format == FormatQuestion.CONSTRUCTION:
            # Juger une perpendiculaire demande de mesurer la figure, pas de lire
            # une réponse : ces questions relèvent de la saisie humaine (module 8).
            lot.ecartees[reponse.code_question] = (
                "construction géométrique — relève de la saisie humaine (module 8)"
            )
            continue

        if question.format == FormatQuestion.QCM:
            probleme, motif = diagnostiquer_qcm(question, reponse)
            if probleme is not None:
                lot.problemes.append(probleme)
                lot.traitees.append(reponse.code_question)
            elif motif:
                lot.ecartees[reponse.code_question] = motif
            else:
                lot.traitees.append(reponse.code_question)  # bonne option cochée
            continue

        admis = codes_competence_admis(question)
        lot.admis_par_question[question.code_question] = set(admis)
        lot.charge.append(_charge_utile(question, reponse, admis))

    return lot


# ── Validation d'une sortie de modèle ────────────────────────────────────────


def valider(
    sortie: SortieDiagnosticContraint,
    admis_par_question: dict[str, set[str]],
    codes_types: set[str],
) -> tuple[list[ProblemeDetecte], list[str]]:
    """Sépare les problèmes recevables des rejets, avec le motif de chaque rejet.

    Les motifs sont rendus tels quels au modèle à la redemande : ils doivent donc
    être lisibles et dire quoi faire, pas seulement constater.
    """
    retenus: list[ProblemeDetecte] = []
    rejets: list[str] = []
    vus: set[str] = set()

    for probleme in sortie.problemes:
        code_q = probleme.code_question
        admis = admis_par_question.get(code_q)

        if admis is None:
            rejets.append(
                f"{code_q} : cette question ne fait pas partie de celles soumises. "
                f"Ne diagnostiquer que les questions fournies."
            )
            continue
        if code_q in vus:
            rejets.append(
                f"{code_q} : deux problèmes pour la même question. Une question ne "
                f"révèle qu'une lacune — garder celle qui explique le plus."
            )
            continue
        if probleme.code_competence not in admis:
            rejets.append(
                f"{code_q} : compétence {probleme.code_competence!r} non admise. "
                f"Codes possibles pour cette question : {', '.join(sorted(admis))}."
            )
            continue
        if probleme.code_type_erreur not in codes_types:
            rejets.append(
                f"{code_q} : type d'erreur {probleme.code_type_erreur!r} inconnu. "
                f"Liste fermée : {', '.join(sorted(codes_types))}."
            )
            continue
        if not probleme.citation.strip():
            rejets.append(
                f"{code_q} : citation vide. Sans elle, un désaccord sur ce problème "
                f"est inarbitrable — citer ce qui est écrit sur la copie."
            )
            continue

        vus.add(code_q)
        retenus.append(probleme)

    return retenus, rejets


# ── Orchestration ────────────────────────────────────────────────────────────


def diagnostiquer(
    *,
    niveau_test: str,
    reponses: list[ReponseEleve],
    client=None,
    copy_id: str = "",
) -> DiagnosticContraint:
    """Diagnostic complet d'une copie.

    `client` est injecté plutôt qu'instancié ici : sans clé d'API, les QCM restent
    diagnosticables intégralement — c'est la moitié mécanique du module, et elle
    doit tourner sans dépendre d'un fournisseur. Passer `None` produit donc un
    diagnostic partiel **et le dit**, au lieu d'échouer.
    """
    lot = preparer(niveau_test, reponses)
    codes_types = set(TypeErreur.objects.values_list("code", flat=True))

    resultat = DiagnosticContraint(
        copy_id=copy_id,
        niveau_test=niveau_test,
        problemes=list(lot.problemes),
        questions_diagnostiquees=list(lot.traitees),
        questions_ecartees=dict(lot.ecartees),
    )

    if not lot.charge:
        return resultat

    if client is None:
        for charge in lot.charge:
            resultat.questions_ecartees[charge["code_question"]] = (
                "aucun client de diagnostic — seuls les QCM ont été traités"
            )
        return resultat

    if not codes_types:
        raise RuntimeError(
            "Le référentiel est vide : lancer `manage.py importer_referentiel` "
            "avant tout diagnostic. Sans lui, aucun code ne peut être validé."
        )

    codes_competences = sorted(
        {code for admis in lot.admis_par_question.values() for code in admis}
    )
    corrections = ""

    for tentative in range(REDEMANDES_MAX + 1):
        reponse_api = client.diagnose_constrained(
            copy_id=copy_id,
            niveau_test=niveau_test,
            questions=lot.charge,
            codes_competences=codes_competences,
            codes_types=sorted(codes_types),
            corrections=corrections,
        )
        resultat.appels_modele += 1

        if not reponse_api.success or reponse_api.data is None:
            logger.warning(
                "[%s] Diagnostic contraint sans réponse : %s",
                copy_id, reponse_api.error,
            )
            for charge in lot.charge:
                resultat.questions_ecartees.setdefault(
                    charge["code_question"],
                    f"le modèle n'a pas répondu ({reponse_api.error or 'erreur inconnue'})",
                )
            return resultat

        retenus, rejets = valider(
            reponse_api.data, lot.admis_par_question, codes_types
        )
        if not rejets:
            resultat.problemes.extend(retenus)
            break

        logger.warning(
            "[%s] Diagnostic contraint — %d sortie(s) refusée(s), tentative %d/%d",
            copy_id, len(rejets), tentative + 1, REDEMANDES_MAX + 1,
        )
        if tentative == REDEMANDES_MAX:
            # Ce qui reste invalide après redemande est abandonné, pas réparé.
            resultat.problemes.extend(retenus)
            resultat.rejets.extend(rejets)
            break
        corrections = "\n".join(f"- {motif}" for motif in rejets)

    diagnostiquees = {p.code_question for p in resultat.problemes}
    for charge in lot.charge:
        code = charge["code_question"]
        if code in diagnostiquees:
            resultat.questions_diagnostiquees.append(code)
        else:
            resultat.questions_ecartees.setdefault(
                code, "aucun problème retenu par le modèle pour cette question"
            )

    return resultat


# ── Diagnostic sans ancrage de question — la mesure « plancher » ─────────────
#
# Pourquoi ce second mode existe
# ------------------------------
# Le mode normal ci-dessus travaille **par question** : il reçoit l'énoncé, la
# compétence évaluée, ses prérequis et ses signatures d'erreur, tous tirés des 280
# questions v2. Les 5 copies du corpus de référence sont de l'**ancien format**
# et n'en portent aucune : le mode normal ne peut pas tourner dessus, donc le
# module 4 n'a rien contre quoi se mesurer tant qu'aucune copie du nouveau format
# n'existe.
#
# Ce mode-ci fait la tâche **plus dure** : la production de l'élève, le catalogue
# des compétences déjà enseignées à ce niveau, les sept types — et rien d'autre.
# Pas de signature à reconnaître. C'est exactement ce qu'a fait l'humain qui a
# tagué le corpus, donc la comparaison est loyale ; et c'est un **plancher**, pas
# la configuration de production : le mode normal, mieux armé, ne peut que faire
# aussi bien ou mieux.
#
# ⚠ LE PIÈGE À NE JAMAIS TENDRE
# ------------------------------
# Il est tentant d'alimenter ce mode avec le champ `Probleme.justification` du
# corpus, puisqu'il est déjà en base et décrit ce qu'on a lu sur la copie. **Ce
# serait mesurer le vide.** Ces justifications sont écrites par le tagueur et
# contiennent déjà le diagnostic en toutes lettres — « nommer les rangs n'est pas
# disponible », « la formule est juste, seul le produit est faux ». Les donner en
# entrée, c'est donner la réponse : le score serait excellent et ne voudrait rien
# dire.
#
# L'entrée doit être la **production brute de l'élève**, transcrite depuis le scan
# et rien de plus. `ProductionEleve.production` porte ce texte, et la commande
# `mesurer_plancher` refuse de tourner sans un fichier de productions distinct.


@dataclass(frozen=True)
class ProductionEleve:
    """Ce que l'élève a écrit, sans aucune interprétation.

    `repere` identifie l'endroit de la copie (« exercice 3b ») — il ne sert qu'à
    relier un problème à sa source et n'a pas besoin d'exister au référentiel.
    """

    repere: str
    enonce: str
    production: str


def catalogue_competences(niveau_test: str) -> list[dict]:
    """Les compétences que l'élève est censé avoir déjà rencontrées.

    Restreint à ce qui précède strictement le niveau du test : un test d'entrée
    **en** 5ème évalue ce qui vient avant la 5ème. Sans cette borne, le modèle se
    verrait proposer les compétences de Terminale pour une copie de 6ème.
    """
    competences = [
        c
        for c in Competence.objects.all().order_by("domaine", "code")
        if deja_enseigne(c.niveau_intro, niveau_test)
    ]
    return [
        {
            "code": c.code,
            "libelle": c.libelle,
            "description": c.description or "",
            "domaine": c.domaine,
            "introduite_en": c.niveau_intro,
        }
        for c in competences
    ]


def diagnostiquer_sans_ancrage(
    *,
    niveau_test: str,
    productions: list[ProductionEleve],
    client,
    copy_id: str = "",
) -> DiagnosticContraint:
    """Diagnostic d'une copie hors référentiel de questions — mesure plancher.

    Aucun QCM n'est court-circuité ici : sans question du référentiel, il n'y a
    pas de table d'options. Tout passe par le modèle, ce qui est précisément ce
    qui rend cette mesure sévère.
    """
    catalogue = catalogue_competences(niveau_test)
    codes_admis = {c["code"] for c in catalogue}
    codes_types = set(TypeErreur.objects.values_list("code", flat=True))

    resultat = DiagnosticContraint(copy_id=copy_id, niveau_test=niveau_test)

    if not codes_admis:
        raise RuntimeError(
            f"Aucune compétence n'est enseignée avant le niveau {niveau_test!r} "
            "dans le référentiel — vérifier l'import du classeur et le niveau donné."
        )

    charge = [
        {
            "repere": p.repere,
            "enonce": p.enonce,
            "production_eleve": p.production.strip() or CITATION_VIDE,
            "zone_vierge": not p.production.strip(),
        }
        for p in productions
    ]
    # Le catalogue tient lieu de contrainte par question : ici, toute compétence
    # déjà enseignée est admissible pour n'importe quel repère.
    admis_par_repere = {c["repere"]: codes_admis for c in charge}
    corrections = ""

    for tentative in range(REDEMANDES_MAX + 1):
        reponse_api = client.diagnose_unanchored(
            copy_id=copy_id,
            niveau_test=niveau_test,
            productions=charge,
            catalogue=catalogue,
            codes_types=sorted(codes_types),
            corrections=corrections,
        )
        resultat.appels_modele += 1

        if not reponse_api.success or reponse_api.data is None:
            logger.warning(
                "[%s] Mesure plancher sans réponse : %s", copy_id, reponse_api.error
            )
            for item in charge:
                resultat.questions_ecartees[item["repere"]] = (
                    f"le modèle n'a pas répondu ({reponse_api.error or 'erreur inconnue'})"
                )
            return resultat

        retenus, rejets = valider(reponse_api.data, admis_par_repere, codes_types)
        if not rejets:
            resultat.problemes.extend(retenus)
            break
        if tentative == REDEMANDES_MAX:
            resultat.problemes.extend(retenus)
            resultat.rejets.extend(rejets)
            break
        corrections = "\n".join(f"- {motif}" for motif in rejets)

    diagnostiques = {p.code_question for p in resultat.problemes}
    for item in charge:
        if item["repere"] in diagnostiques:
            resultat.questions_diagnostiquees.append(item["repere"])
        else:
            resultat.questions_ecartees.setdefault(
                item["repere"], "aucun problème retenu par le modèle"
            )

    return resultat
