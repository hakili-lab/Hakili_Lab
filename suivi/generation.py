"""
Génération à la demande des sujets T1 (confirmation des hypothèses), T3
(vérification après remédiation) et T4/T5 (contrôle de rétention) — module 5.

`generer_sujet_confirmation` (T1) est un miroir à la demande de
`_generer_sujet_confirmation` (`correction_web/taches.py`), qui reste le
chemin normal : elle génère et persiste (comme `Document`) un premier sujet
T1 en sous-produit automatique d'une correction T0. Cette fonction-ci couvre
le cas où l'enseignant veut le regénérer plus tard — échec initial, nouvelles
hypothèses écrites depuis, sujet perdu — sans repasser par une correction.
Pour T3/T4/T5, il n'y a pas d'équivalent automatique : le timing (fin de
volume horaire, +45 jours, +3 mois) est une décision humaine, c'est
l'enseignant qui déclenche la génération depuis le profil élève.

Le sujet généré ici n'est jamais persisté (pas de `Document`) : les problèmes
qu'il cible peuvent changer d'état entre deux visites, un PDF figé irait vite
périmé — même raison que `suivi/plan.py` / `fiche_remediation` (le plan n'est
pas stocké non plus).
"""
from __future__ import annotations

import logging

from suivi.models import EtatProbleme, Probleme, Session, TypeEvaluation

logger = logging.getLogger(__name__)

#: Problème ciblé par chaque type — respecte strictement
#: `Probleme.TRANSITIONS_PERMISES` (suivi/models.py) : seul un problème
#: `en_remediation` peut avancer vers `resolu`/`non_resolu` (T3), seul un
#: problème `resolu` peut avancer vers `regresse`/`clos` (T4, T5).
ETAT_CIBLE: dict[str, str] = {
    TypeEvaluation.T3: EtatProbleme.EN_REMEDIATION,
    TypeEvaluation.T4: EtatProbleme.RESOLU,
    TypeEvaluation.T5: EtatProbleme.RESOLU,
}


def problemes_a_verifier(session: Session, type_evaluation: str) -> list[Probleme]:
    """Les problèmes que ce type d'évaluation doit recontrôler.

    Lève `ValueError` pour un type sans sujet de vérification (T0, T1 — leurs
    sujets suivent un autre chemin, voir `correction_web/taches.py`).
    """
    etat = ETAT_CIBLE.get(type_evaluation)
    if etat is None:
        raise ValueError(
            f"Pas de sujet de vérification pour le type « {type_evaluation} »."
        )
    return list(
        session.problemes.filter(etat=etat).select_related("competence", "type_erreur")
    )


def _client():
    """Même client best-effort que le module 4 — une clé d'API absente ne doit
    jamais faire planter l'écran qui propose de générer un sujet."""
    try:
        from src.api.claude_client import ClaudeClient

        return ClaudeClient()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[module 5] Aucun client disponible (%s).", exc)
        return None


def generer_sujet_verification(session: Session, type_evaluation: str):
    """Génère le sujet T3/T4/T5 pour cette session, ou `None` si rien à
    vérifier ou si la génération a échoué.

    Retourne un `VerificationSubject` (`src.models.domain`), prêt pour
    `generate_remediation_pdf`. Best-effort, comme le reste du pipeline de
    génération : appelé depuis une vue, pas depuis la correction, une panne
    ici ne fait rien perdre — elle empêche seulement la génération.
    """
    from src.models.domain import VerificationItem, VerificationRequest
    from src.pipeline.orchestrator import validate_verification

    problemes = problemes_a_verifier(session, type_evaluation)
    if not problemes:
        return None

    client = _client()
    if client is None:
        return None

    request = VerificationRequest(
        copy_id=f"verif-{session.pk}-{type_evaluation.lower()}",
        type_evaluation=type_evaluation,
        items=[
            VerificationItem(
                competence_label=p.competence.libelle,
                type_erreur_label=p.type_erreur.libelle,
                contexte=p.justification,
            )
            for p in problemes
        ],
    )
    reponse = client.generate_verification_subject(request)
    if not reponse.success or reponse.data is None:
        logger.warning(
            "[session %s] Génération %s échouée (%s)",
            session.pk, type_evaluation, reponse.error,
        )
        return None

    validation = validate_verification(reponse.data, request)
    if not validation.valid:
        logger.warning(
            "[session %s] Sujet %s invalide, non produit (%s)",
            session.pk, type_evaluation,
            [i.message for i in validation.issues if i.severity == "error"],
        )
        return None

    logger.info(
        "[session %s] Sujet %s généré — %d problème(s) ciblé(s).",
        session.pk, type_evaluation, len(problemes),
    )
    return validation.data


def generer_sujet_confirmation(session: Session):
    """Génère le sujet T1 (confirmation des hypothèses) pour cette session, ou
    `None` si rien à confirmer ou si la génération a échoué.

    Cible `session.problemes` en état `hypothese` — les mêmes que
    `_generer_sujet_confirmation` (`correction_web/taches.py`) et que l'écran
    « Lacunes à confirmer » (`suivi_web/views.py::session_detail`). Best-effort
    et jamais persisté, comme `generer_sujet_verification` : voir la docstring
    de ce module.
    """
    from src.models.domain import ConfirmationHypothesis, ConfirmationRequest
    from src.pipeline.orchestrator import validate_confirmation

    hypotheses = list(
        session.problemes.filter(etat=EtatProbleme.HYPOTHESE)
        .select_related("competence", "type_erreur")
    )
    if not hypotheses:
        return None

    client = _client()
    if client is None:
        return None

    request = ConfirmationRequest(
        copy_id=f"confirmation-{session.pk}",
        hypotheses=[
            ConfirmationHypothesis(
                competence_label=p.competence.libelle,
                type_erreur_label=p.type_erreur.libelle,
                justification=p.justification,
                is_att=p.type_erreur_id == "ATT",
            )
            for p in hypotheses
        ],
    )
    reponse = client.generate_confirmation_subject(request)
    if not reponse.success or reponse.data is None:
        logger.warning(
            "[session %s] Génération T1 échouée (%s)", session.pk, reponse.error,
        )
        return None

    validation = validate_confirmation(reponse.data, request)
    if not validation.valid:
        logger.warning(
            "[session %s] Sujet T1 invalide, non produit (%s)",
            session.pk,
            [i.message for i in validation.issues if i.severity == "error"],
        )
        return None

    logger.info(
        "[session %s] Sujet T1 généré — %d hypothèse(s) ciblée(s).",
        session.pk, len(hypotheses),
    )
    return validation.data
