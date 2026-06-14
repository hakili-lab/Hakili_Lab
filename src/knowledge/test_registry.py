"""
TestRegistry — Catalogue des tests standards Hakili Lab.

Pour chaque test pré-défini, charge automatiquement :
  - L'énoncé (texte extrait du fichier DOCX dans data/Documents/)
  - Le barème Rubric (construit depuis le YAML data/knowledge/bareme_test_*.yaml)
  - Le bareme_id RAG correspondant

Utilisation dans le pipeline :
    registry = get_registry()
    test = registry.get_test("hakili_3e_v1")
    rubric      = test.rubric        # Rubric Pydantic prêt à l'emploi
    subject_text = test.subject_text  # Texte de l'énoncé
    bareme_id    = test.bareme_id
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.knowledge.answer_loader import get_answer_loader

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent.parent
_DOCS_DIR = _ROOT / "data" / "Documents"
_KB_DIR = _ROOT / "data" / "knowledge"

# ── Catalogue des tests Hakili ────────────────────────────────────────────────

_TEST_CATALOG: dict[str, dict] = {
    "hakili_3e_v1": {
        "label": "Test diagnostique Hakili 3e v1",
        "description": "Évalue les acquis de la 6e à la 4e (calcul et géométrie)",
        "niveaux": "6e · 5e · 4e",
        "docx_filename": "Hakilisso test de niveau 3e.docx",
        "bareme_yaml": "bareme_test_3e.yaml",
        "corrige_yaml": "corrige_test_3e.yaml",
    },
    "hakili_3e_v2": {
        "label": "Test diagnostique Hakili 3e v2",
        "description": "Évalue les acquis de la 6e à la 4e (calcul et géométrie) — version 2",
        "niveaux": "6e · 5e · 4e",
        "docx_filename": "Test-niveau 3ieme v2.docx",
        "bareme_yaml": "bareme_test_3e_v2.yaml",
        "corrige_yaml": "corrige_test_3e_v2.yaml",
    },
    "hakili_6e_v1": {
        "label": "Test diagnostique Hakili 6e v1",
        "description": "Évalue les acquis du CE1 au CM2 (calcul et géométrie)",
        "niveaux": "CE1 · CE2 · CM1 · CM2",
        "docx_filename": "TEST DE NIVEAU,6eme,GROUPE 1.docx",
        "bareme_yaml": "bareme_test_6e.yaml",
        "corrige_yaml": "corrige_test_6e.yaml",
    },
}


@dataclass
class HakiliTest:
    """Test Hakili pré-chargé — prêt à injecter dans run_single_copy()."""
    bareme_id: str
    label: str
    description: str
    niveaux: str
    subject_text: str
    rubric: "Rubric"  # type: ignore[type-arg]
    total_questions: int
    official_answers: str = ""  # Corrigé officiel formaté pour injection dans le prompt


def _extract_docx_text(docx_path: Path) -> str:
    """Extrait le texte brut d'un fichier DOCX (tous paragraphes non vides)."""
    try:
        import docx  # python-docx
        doc = docx.Document(str(docx_path))
        lines = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                lines.append(text)
        # Inclure aussi les tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    text = cell.text.strip()
                    if text and text not in lines:
                        lines.append(text)
        return "\n".join(lines)
    except ImportError:
        logger.error("python-docx non installé — impossible d'extraire l'énoncé DOCX.")
        return ""
    except Exception as exc:
        logger.error("Erreur extraction DOCX %s : %s", docx_path.name, exc)
        return ""


def _build_rubric_from_yaml(bareme_yaml_path: Path) -> tuple["Rubric", int]:
    """
    Construit un objet Rubric Pydantic à partir d'un fichier bareme_test_*.yaml.

    Retourne (rubric, total_questions).
    """
    from src.models.domain import Rubric, RubricItem

    try:
        raw = yaml.safe_load(bareme_yaml_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Erreur lecture barème YAML %s : %s", bareme_yaml_path.name, exc)
        return Rubric(subject="mathematics", total_points=0, items=[]), 0

    items: list[RubricItem] = []
    for section in ("questions_numeriques", "questions_geometriques"):
        for q in raw.get(section, []):
            qid = q.get("id", "")
            label = q.get("enonce_court", qid)
            pts = float(q.get("points_originaux", 1.0))
            if qid:
                items.append(RubricItem(id=qid, label=label, max_score=pts))

    meta = raw.get("meta", {})
    total_pts = float(meta.get("total_possible") or sum(i.max_score for i in items))
    rubric = Rubric(
        subject="mathematics",
        total_points=total_pts,
        items=items,
    )
    return rubric, len(items)


class TestRegistry:
    """
    Singleton — chargé une fois en début de session.

    Charge et met en cache les tests Hakili (énoncés + barèmes).
    """

    def __init__(self) -> None:
        self._tests: dict[str, HakiliTest] = {}
        self._load_all()

    def _load_all(self) -> None:
        for test_id, cfg in _TEST_CATALOG.items():
            docx_path = _DOCS_DIR / cfg["docx_filename"]
            yaml_path = _KB_DIR / cfg["bareme_yaml"]

            if not docx_path.exists():
                logger.warning(
                    "Test '%s' — DOCX introuvable : %s", test_id, docx_path
                )
            if not yaml_path.exists():
                logger.warning(
                    "Test '%s' — barème YAML introuvable : %s", test_id, yaml_path
                )
                continue

            subject_text = _extract_docx_text(docx_path) if docx_path.exists() else ""
            rubric, total = _build_rubric_from_yaml(yaml_path)

            # Chargement du corrigé officiel
            official_answers = get_answer_loader().get_official_answers(test_id)

            self._tests[test_id] = HakiliTest(
                bareme_id=test_id,
                label=cfg["label"],
                description=cfg["description"],
                niveaux=cfg["niveaux"],
                subject_text=subject_text,
                rubric=rubric,
                total_questions=total,
                official_answers=official_answers,
            )
            corrige_status = f"corrigé {len(official_answers)} chars" if official_answers else "sans corrigé"
            logger.info(
                "Test chargé : %s (%d questions, énoncé %d chars, %s)",
                test_id, total, len(subject_text), corrige_status,
            )

    def available_tests(self) -> dict[str, HakiliTest]:
        return dict(self._tests)

    def get_test(self, test_id: str) -> HakiliTest | None:
        return self._tests.get(test_id)

    @property
    def ids(self) -> list[str]:
        return list(self._tests.keys())


# ── Singleton module-level ────────────────────────────────────────────────────

_registry: TestRegistry | None = None


def get_registry() -> TestRegistry:
    global _registry
    if _registry is None:
        _registry = TestRegistry()
    return _registry
