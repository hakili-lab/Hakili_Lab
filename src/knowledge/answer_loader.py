"""
AnswerLoader — charge les corrigés officiels Hakili Lab et les formate
en bloc texte injecté dans le prompt de correction.

Fonctionnement :
  1. Charge corrige_test_*.yaml depuis data/knowledge/ au démarrage.
  2. get_official_answers(test_id) → bloc texte prêt à injecter dans le prompt.
  3. Si le test_id est absent ou le fichier introuvable → retourne "" (pas de crash).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_KB_DIR = Path(__file__).parent.parent.parent / "data" / "knowledge"


class OfficialAnswer:
    """Réponse officielle pour une question donnée."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.id: str = data["id"]
        self.reponse: str = data.get("reponse", "")
        self.solution: str = (data.get("solution") or "").strip()

    def to_text(self) -> str:
        lines = [f"{self.id} → {self.reponse}"]
        if self.solution:
            for line in self.solution.splitlines():
                lines.append(f"   {line}")
        return "\n".join(lines)


class AnswerLoader:
    """
    Singleton — chargé une seule fois par session.

    Utilisation :
        loader = get_answer_loader()
        answers_text = loader.get_official_answers("hakili_3e_v1")
    """

    def __init__(self) -> None:
        self._answers: dict[str, list[OfficialAnswer]] = {}
        self._load_all()

    def _load_all(self) -> None:
        corrige_files = list(_KB_DIR.glob("corrige_test_*.yaml"))
        if not corrige_files:
            logger.warning("Aucun fichier corrige_test_*.yaml trouvé dans %s", _KB_DIR)
            return
        for path in corrige_files:
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    continue
                test_id = raw.get("meta", {}).get("test_id", path.stem)
                all_answers: list[OfficialAnswer] = []
                for section in ("questions_numeriques", "questions_geometriques"):
                    for item in raw.get(section, []):
                        all_answers.append(OfficialAnswer(item))
                self._answers[test_id] = all_answers
                logger.info(
                    "Corrigé chargé : %s (%d réponses officielles)",
                    test_id, len(all_answers),
                )
            except Exception as exc:
                logger.error("Erreur lecture corrigé %s : %s", path.name, exc)

    def get_official_answers(self, test_id: str) -> str:
        """
        Retourne un bloc texte formaté pour injection dans le prompt de correction.
        Retourne "" si le test_id est inconnu (pas de crash, pipeline continue).
        """
        answers = self._answers.get(test_id)
        if not answers:
            return ""

        lines = [
            "## Corrigé officiel — utilise ces réponses comme référence de correction",
            "",
            "Ces réponses sont extraites du corrigé officiel Hakili Lab.",
            "Pour chaque question, compare la réponse de l'élève à la réponse officielle ci-dessous.",
            "Ne te fie PAS à ton propre calcul si une réponse officielle est fournie ici.",
            "",
        ]
        for ans in answers:
            lines.append(ans.to_text())
            lines.append("")

        return "\n".join(lines)

    def available_tests(self) -> list[str]:
        return list(self._answers.keys())


# ── Singleton module-level ────────────────────────────────────────────────────

_loader: AnswerLoader | None = None


def get_answer_loader() -> AnswerLoader:
    global _loader
    if _loader is None:
        _loader = AnswerLoader()
    return _loader
