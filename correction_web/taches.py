"""
Exécution du pipeline en arrière-plan.

Choix : un thread, pas une file de tâches
-----------------------------------------
Une file (Redis + RQ, ou Celery) serait plus robuste, mais ajoute un service à
déployer et à surveiller. Le besoin réel est un enseignant qui corrige ses copies
une par une : une poignée d'exécutions simultanées au plus. Un thread par correction
suffit, et le suivi de progression passe par la base — donc il fonctionne même si la
requête suivante est servie par un autre processus.

Limite assumée, et il faut la connaître : si le processus est arrêté (redéploiement,
mise en veille de l'hébergeur) pendant qu'un thread travaille, la correction reste
bloquée dans un état « en cours ». `relancer_si_bloquee` détecte ce cas sur la durée
et le signale, plutôt que de laisser tourner un rond de progression indéfiniment.
À remplacer par une vraie file si le volume augmente.

Attention aux connexions de base dans un thread : Django en ouvre une par thread et
ne la referme pas tout seul. Sans `close_old_connections()` à la fin, elles
s'accumulent jusqu'à saturer le pool côté Neon.
"""
from __future__ import annotations

import logging
import threading
from datetime import timedelta
from pathlib import Path

from django.db import close_old_connections
from django.utils import timezone

from correction_web.models import ETATS_EN_COURS, Correction, EtatCorrection
from correction_web.serialisation import deserialiser, serialiser

logger = logging.getLogger(__name__)

#: Au-delà, une correction « en cours » est considérée comme abandonnée.
#: Le pipeline complet tient largement sous 5 minutes (transcription + correction
#: mesurées à 60-90 s) ; 15 minutes laisse de la marge à une API lente sans laisser
#: un état bloqué toute la journée.
DELAI_ABANDON = timedelta(minutes=15)

_LIBELLES_ETAPE = {
    "ingestion": "Lecture de la copie",
    "transcription": "Transcription de l'écriture",
    "correction": "Correction question par question",
    "rag": "Recherche dans le programme officiel",
    "diagnostic": "Diagnostic pédagogique",
    "remediation": "Plan de remédiation",
    "export": "Génération du rapport",
}


def _rapporteur(correction_id: int):
    """Callback `on_progress` du pipeline → progression en base."""

    def rapporter(etape: str, pourcentage: int) -> None:
        try:
            Correction.objects.filter(pk=correction_id).update(
                etape=_LIBELLES_ETAPE.get(etape, etape),
                progression=max(0, min(100, pourcentage)),
                maj_le=timezone.now(),
            )
        except Exception:  # noqa: BLE001
            # La progression est un confort : son échec ne doit jamais interrompre
            # une correction déjà lancée.
            logger.debug("[%s] Progression non enregistrée.", correction_id)

    return rapporter


def _dans_un_thread(cible, *args) -> None:
    def enveloppe():
        try:
            cible(*args)
        finally:
            # Sans cela, une connexion reste ouverte par thread et le pool sature.
            close_old_connections()

    threading.Thread(target=enveloppe, daemon=True).start()


# ── Phase A, première moitié : transcription ─────────────────────────────────

def lancer_transcription(
    correction: Correction,
    chemins: list[Path],
    rubric,
    test,
    sujet: Path | None = None,
) -> None:
    """`test` vaut None en mode libre ; `sujet` est alors le PDF de l'énoncé, dont
    le pipeline extrait lui-même le barème."""
    correction.etat = EtatCorrection.TRANSCRIPTION
    correction.etape = "Lecture de la copie"
    correction.progression = 2
    correction.save(update_fields=["etat", "etape", "progression", "maj_le"])
    _dans_un_thread(_executer_transcription, correction.pk, chemins, rubric, test, sujet)


def _executer_transcription(
    correction_id: int, chemins: list[Path], rubric, test, sujet: Path | None = None
) -> None:
    from src.pipeline.pipeline import run_transcription

    correction = Correction.objects.get(pk=correction_id)
    try:
        resultat = run_transcription(
            copy_id=correction.copy_id,
            identifiant_hakili=correction.identifiant_hakili,
            student_name=f"{correction.eleve_prenom} {correction.eleve_nom}".strip(),
            file_paths=chemins,
            rubric=rubric,
            subject_text=getattr(test, "subject_text", ""),
            subject_file_path=sujet,
            expert_instructions=correction.instructions_expert,
            bareme_id=correction.bareme_id,
            official_answers=getattr(test, "official_answers", ""),
            on_progress=_rapporteur(correction_id),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("[%s] Transcription interrompue : %s", correction.copy_id, exc)
        correction.echouer(f"Transcription interrompue : {exc}")
        return

    correction.resultat = serialiser(resultat)
    correction.erreurs = list(resultat.errors or [])
    if resultat.errors or resultat.transcription is None:
        correction.etat = EtatCorrection.ECHEC
    else:
        # Arrêt volontaire : l'enseignant relit la transcription avant correction.
        correction.etat = EtatCorrection.RELECTURE
        correction.etape = "Relecture de la transcription"
        correction.progression = 40
    correction.save()


# ── Phase A, seconde moitié : correction ─────────────────────────────────────

def lancer_correction(correction: Correction) -> None:
    correction.etat = EtatCorrection.CORRECTION
    correction.etape = "Correction question par question"
    correction.progression = 45
    correction.save(update_fields=["etat", "etape", "progression", "maj_le"])
    _dans_un_thread(_executer_correction, correction.pk)


def _executer_correction(correction_id: int) -> None:
    from src.pipeline.pipeline import run_grading

    correction = Correction.objects.get(pk=correction_id)
    try:
        resultat = run_grading(
            result=deserialiser(correction.resultat),
            on_progress=_rapporteur(correction_id),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("[%s] Correction interrompue : %s", correction.copy_id, exc)
        correction.echouer(f"Correction interrompue : {exc}")
        return

    correction.resultat = serialiser(resultat)
    correction.erreurs = list(resultat.errors or [])
    if resultat.grade is None:
        correction.etat = EtatCorrection.ECHEC
    else:
        # Second arrêt : l'enseignant valide ou corrige chaque note proposée.
        correction.etat = EtatCorrection.VALIDATION
        correction.etape = "Validation des notes"
        correction.progression = 60
    correction.save()


# ── Dépôt en lot : Phase A complète, sans arrêt de relecture ─────────────────

def lancer_phase_a_complete(correction: Correction, chemins: list[Path], rubric, test) -> None:
    """Transcription **et** correction d'affilée, sans l'écran de relecture.

    Relire trente transcriptions une par une coûterait plus de temps à l'enseignant
    que la correction elle-même : c'est le choix déjà fait côté Streamlit pour le
    mode lot, conservé tel quel.

    En revanche, le **tableau de validation est conservé** — contrairement au mode
    lot de Streamlit, qui produisait des rapports complets sans qu'aucun enseignant
    ait vu une seule note. C'était en contradiction avec D-CEO-16, qui pose que
    « la correction automatique sans validation est inacceptable pour un document
    officiel ». Ici, déposer trente copies reste une seule action ; elles arrivent
    ensuite dans la liste des corrections, à valider une par une quand l'enseignant
    a le temps.
    """
    correction.etat = EtatCorrection.TRANSCRIPTION
    correction.etape = "Lecture de la copie"
    correction.progression = 2
    correction.save(update_fields=["etat", "etape", "progression", "maj_le"])
    _dans_un_thread(_executer_phase_a_complete, correction.pk, chemins, rubric, test)


def _executer_phase_a_complete(correction_id: int, chemins: list[Path], rubric, test) -> None:
    from src.pipeline.pipeline import run_phase_a

    correction = Correction.objects.get(pk=correction_id)
    try:
        resultat = run_phase_a(
            copy_id=correction.copy_id,
            identifiant_hakili=correction.identifiant_hakili,
            student_name=f"{correction.eleve_prenom} {correction.eleve_nom}".strip(),
            file_paths=chemins,
            rubric=rubric,
            subject_text=getattr(test, "subject_text", ""),
            expert_instructions=correction.instructions_expert,
            bareme_id=correction.bareme_id,
            official_answers=getattr(test, "official_answers", ""),
            on_progress=_rapporteur(correction_id),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("[%s] Correction interrompue : %s", correction.copy_id, exc)
        correction.echouer(f"Correction interrompue : {exc}")
        return

    correction.resultat = serialiser(resultat)
    correction.erreurs = list(resultat.errors or [])
    if resultat.grade is None:
        correction.etat = EtatCorrection.ECHEC
    else:
        correction.etat = EtatCorrection.VALIDATION
        correction.etape = "Validation des notes"
        correction.progression = 60
    correction.save()


# ── Phase B : diagnostic, remédiation, rapport ───────────────────────────────

def lancer_diagnostic(correction: Correction) -> None:
    correction.etat = EtatCorrection.DIAGNOSTIC
    correction.etape = "Recherche dans le programme officiel"
    correction.progression = 65
    correction.save(update_fields=["etat", "etape", "progression", "maj_le"])
    _dans_un_thread(_executer_diagnostic, correction.pk)


def _ancrage_referentiel(niveau_test: str):
    """Fonction d'ancrage passée au pipeline.

    Le pipeline ne connaît pas le référentiel — il vit dans une application Django
    et `src/` doit rester indépendant de tout framework. On lui passe donc de quoi
    construire son contexte, sans qu'il ait à savoir d'où il vient.

    Retourne `None` si le test n'est pas au référentiel (mode libre, ancien test) :
    le pipeline retombe alors sur son ancrage historique.
    """
    if not niveau_test:
        return None

    def ancrer(codes_questions: list[str]) -> tuple[str, list[dict]]:
        from referentiel.contexte import contexte_diagnostic, lacunes_competences

        return (
            contexte_diagnostic(niveau_test, codes_questions),
            lacunes_competences(niveau_test, codes_questions),
        )

    return ancrer


def _niveau_test(bareme_id: str) -> str:
    """`urie_3eme` → `3eme`. Vide pour un test hors référentiel."""
    return bareme_id[len("urie_"):] if bareme_id.startswith("urie_") else ""


def _executer_diagnostic(correction_id: int) -> None:
    from src.pipeline.pipeline import run_phase_b

    correction = Correction.objects.get(pk=correction_id)
    try:
        resultat = run_phase_b(
            result=deserialiser(correction.resultat),
            on_progress=_rapporteur(correction_id),
            ancrage=_ancrage_referentiel(_niveau_test(correction.bareme_id)),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("[%s] Diagnostic interrompu : %s", correction.copy_id, exc)
        correction.echouer(f"Diagnostic interrompu : {exc}")
        return

    correction.resultat = serialiser(resultat)
    correction.erreurs = list(resultat.errors or [])
    correction.etat = (
        EtatCorrection.ECHEC if resultat.errors else EtatCorrection.TERMINEE
    )
    correction.etape = "Terminée"
    correction.progression = 100
    correction.save()


# ── Corrections abandonnées ──────────────────────────────────────────────────

def signaler_si_abandonnee(correction: Correction) -> bool:
    """Passe en échec une correction « en cours » qui ne bouge plus.

    Le processus qui la traitait a pu être arrêté — redéploiement, mise en veille.
    Sans ce contrôle, l'enseignant verrait une barre de progression tourner
    indéfiniment sans jamais comprendre pourquoi.
    """
    if correction.etat not in ETATS_EN_COURS:
        return False
    if timezone.now() - correction.maj_le < DELAI_ABANDON:
        return False

    logger.warning(
        "[%s] Correction abandonnée après %s sans progression.",
        correction.copy_id,
        DELAI_ABANDON,
    )
    correction.echouer(
        "Le traitement s'est interrompu (le serveur a probablement redémarré). "
        "Relancez la correction de cette copie."
    )
    return True
