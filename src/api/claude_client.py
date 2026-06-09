import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

import anthropic
from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.models.domain import (
    ClaudeResponse,
    CopyGrade,
    DiagnosticResult,
    PageTranscription,
    Rubric,
    RubricItem,
    RemediationSubject,
    TranscriptionResult,
)

_MAX_PAGES_PER_BATCH = 3   # 3 pages par appel → 3× moins d'appels facturés
_TOKENS_PER_BATCH = 4096  # 4096 nécessaire pour 3 pages de copie math sans troncature

_MEDIA_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# ── Tool schemas (tool_use = JSON garanti correctement échappé par l'API) ─────

_TRANSCRIPTION_TOOL: dict[str, Any] = {
    "name": "save_transcription",
    "description": "Sauvegarde la transcription structurée de la copie manuscrite.",
    "input_schema": {
        "type": "object",
        "properties": {
            "copy_id": {"type": "string"},
            "global_quality": {"type": "string", "enum": ["good", "medium", "poor"]},
            "pages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "page_number": {"type": "integer"},
                        "content": {
                            "type": "string",
                            "description": "Tout le texte manuscrit de la page, transcrit mot pour mot.",
                        },
                        "formulas": {
                            "type": "array",
                            "description": "Liste de chaînes de caractères — chaque formule est une STRING simple, ex: 'x^2 + 2x + 1 = 0'. Ne pas utiliser d'objets.",
                            "items": {"type": "string"},
                        },
                        "diagrams": {
                            "type": "array",
                            "description": "Liste de chaînes de caractères décrivant chaque schéma visible. Ne pas utiliser d'objets.",
                            "items": {"type": "string"},
                        },
                        "uncertainties": {
                            "type": "array",
                            "description": "Liste de chaînes de caractères signalant les zones illisibles ou ambiguës, ex: 'Ligne 3 illisible'. Ne pas utiliser d'objets.",
                            "items": {"type": "string"},
                        },
                        "confidence": {"type": "number"},
                    },
                    "required": ["page_number", "content", "formulas", "diagrams",
                                 "uncertainties", "confidence"],
                },
            },
        },
        "required": ["copy_id", "global_quality", "pages"],
    },
}

_GRADING_TOOL: dict[str, Any] = {
    "name": "save_grading",
    "description": "Sauvegarde les résultats de correction de la copie.",
    "input_schema": {
        "type": "object",
        "properties": {
            "copy_id": {"type": "string"},
            "total_score": {"type": "integer"},
            "total_possible": {"type": "integer"},
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "rubric_item_id": {"type": "string"},
                        "score": {"type": "integer", "enum": [0, 1]},
                        "confidence": {"type": "number"},
                        "comment": {"type": "string"},
                        "observed_answer": {"type": "string"},
                        "requires_review": {"type": "boolean"},
                    },
                    "required": ["rubric_item_id", "score", "confidence", "comment",
                                 "observed_answer", "requires_review"],
                },
            },
        },
        "required": ["copy_id", "total_score", "total_possible", "questions"],
    },
}

_QUESTIONS_EXTRACTION_TOOL: dict[str, Any] = {
    "name": "save_questions",
    "description": "Sauvegarde la liste des questions identifiées dans la transcription.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "description": "Liste ordonnée de toutes les questions et sous-questions.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Identifiant court et cohérent, ex : Q1, Q2a, Q2b, Q3.",
                        },
                        "label": {
                            "type": "string",
                            "description": "Libellé court de la question, ex : 'Calcul de volume'.",
                        },
                    },
                    "required": ["id", "label"],
                },
            },
        },
        "required": ["questions"],
    },
}

_RUBRIC_EXTRACTION_TOOL: dict[str, Any] = {
    "name": "save_rubric",
    "description": "Extrait les items du barème depuis le document fourni.",
    "input_schema": {
        "type": "object",
        "properties": {
            "total_points": {
                "type": "integer",
                "description": "Nombre total de points du barème.",
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Identifiant de la question, ex : Q1, Q2a, Q2b.",
                        },
                        "label": {
                            "type": "string",
                            "description": "Libellé ou description de la question.",
                        },
                        "parent_id": {
                            "type": "string",
                            "description": "ID de la question parente si sous-question, sinon null.",
                        },
                    },
                    "required": ["id", "label"],
                },
            },
        },
        "required": ["total_points", "items"],
    },
}


class _ExtractedRubric(BaseModel):
    total_points: int = 0
    items: list[dict] = []


# ── Fallback JSON repair (utilisé uniquement pour diagnose) ───────────────────

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")
_CLOSE_MAP: dict[str, str] = {"[": "]", "{": "}"}


def _close_json(text: str) -> str:
    stack: list[str] = []
    in_string = False
    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\" and in_string:
            i += 2
            continue
        if c == '"':
            in_string = not in_string
        elif not in_string:
            if c in ("{", "["):
                stack.append(c)
            elif c in ("}", "]") and stack:
                stack.pop()
        i += 1
    return text + "".join(_CLOSE_MAP[c] for c in reversed(stack))


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code in (429, 529)
    return isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError))


_retry = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(6),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    reraise=True,
)


class ClaudeClient:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._transcription_prompt = self._load_prompt("transcription_prompt.md")
        self._grading_prompt = self._load_prompt("grading_prompt.md")
        self._diagnostic_prompt = self._load_prompt("diagnostic_prompt.md")
        self._remediation_subject_prompt = self._load_prompt("remediation_subject_prompt.md")

    def _load_prompt(self, filename: str) -> str:
        prompt_path = Path(__file__).parent.parent.parent / "prompts" / filename
        return prompt_path.read_text(encoding="utf-8")

    # ── Transcription ──────────────────────────────────────────────────────────

    def transcribe(self, copy_id: str, image_paths: list[Path]) -> ClaudeResponse:
        logger.info("[%s] Claude transcription — modèle : %s | pages : %d",
                    copy_id, settings.claude_model_heavy, len(image_paths))
        if len(image_paths) <= _MAX_PAGES_PER_BATCH:
            return self._transcribe_batch(copy_id, image_paths, page_offset=0)
        return self._transcribe_batched(copy_id, image_paths)

    def _transcribe_batched(self, copy_id: str, image_paths: list[Path]) -> ClaudeResponse:
        all_pages: list[PageTranscription] = []
        qualities: list[str] = []

        for start in range(0, len(image_paths), _MAX_PAGES_PER_BATCH):
            batch = image_paths[start : start + _MAX_PAGES_PER_BATCH]
            resp = self._transcribe_batch(copy_id, batch, page_offset=start)
            if not resp.success or resp.data is None:
                return resp
            data: TranscriptionResult = resp.data
            all_pages.extend(data.pages)
            qualities.append(data.global_quality)

        global_quality: str = (
            "poor" if "poor" in qualities
            else "medium" if "medium" in qualities
            else "good"
        )
        merged = TranscriptionResult(
            copy_id=copy_id,
            global_quality=global_quality,  # type: ignore[arg-type]
            pages=all_pages,
        )
        avg_conf = sum(p.confidence for p in all_pages) / len(all_pages) if all_pages else 0.5
        return ClaudeResponse(
            success=True,
            data=merged,
            confidence=avg_conf,
            raw_response=f"[batched {len(all_pages)} pages]",
            error=None,
        )

    @_retry
    def _transcribe_batch(
        self, copy_id: str, image_paths: list[Path], page_offset: int = 0
    ) -> ClaudeResponse:
        page_hint = (
            f"\nCes images sont les pages {page_offset + 1} à {page_offset + len(image_paths)}."
            f" Utilise page_number à partir de {page_offset + 1}."
            if page_offset > 0 else ""
        )

        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": self._transcription_prompt,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": f"copy_id : {copy_id}{page_hint}",
            },
            *[
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": self._media_type(path),
                        "data": self._encode_image(path),
                    },
                }
                for path in image_paths
            ],
        ]

        response = self.client.messages.create(
            model=settings.claude_model_heavy,
            max_tokens=_TOKENS_PER_BATCH,
            temperature=0,
            tools=[_TRANSCRIPTION_TOOL],
            tool_choice={"type": "tool", "name": "save_transcription"},
            messages=[{"role": "user", "content": content}],
        )

        return self._extract_tool_result(response, TranscriptionResult)

    # ── Correction ────────────────────────────────────────────────────────────

    @_retry
    def grade(
        self,
        transcription: TranscriptionResult,
        rubric: Rubric,
        subject_text: str,
        expert_instructions: str = "",
        official_answers: str = "",
        temperature: float = 0,
    ) -> ClaudeResponse:
        logger.info("[%s] Claude correction — modèle : %s",
                    transcription.copy_id, settings.claude_model_heavy)
        expert_block = (
            f"\n\nINSTRUCTIONS EXPERT:\n{expert_instructions}"
            if expert_instructions.strip() else ""
        )
        official_block = (
            f"\n\n{official_answers}"
            if official_answers.strip() else ""
        )
        auto_block = (
            "\n\nINSTRUCTION SPÉCIALE : Aucun barème ni corrigé fourni. "
            "Procède en trois étapes :\n"
            "1. Identifie toutes les questions mathématiques visibles dans la transcription. "
            "Génère les identifiants Q1, Q2a, Q2b, etc.\n"
            "2. Pour chaque question identifiée, RÉSOUS-LA TOI-MÊME pour obtenir la réponse correcte "
            "de référence — tu es mathématicien, utilise tes connaissances.\n"
            "3. Compare la réponse de l'élève (transcription) avec ta solution. "
            "Attribue 1 si l'élève a la bonne réponse, 0 sinon. "
            "Dans le commentaire, indique brièvement ce que l'élève a fait (juste ou faux) et, "
            "si faux, ce que valait la réponse correcte.\n"
            "Fixe total_possible = nombre de questions identifiées.\n"
            "Si aucune question n'est identifiable (transcription vide), retourne une entrée unique : "
            "rubric_item_id='Q1', score=0, confidence=0.1, requires_review=true, "
            "comment='Copie illisible — révision manuelle requise', observed_answer='[ILLISIBLE]', "
            "total_possible=1."
            if not rubric.items else ""
        )

        prompt = (
            f"{self._grading_prompt}{auto_block}{official_block}{expert_block}"
            f"\n\nÉNONCÉ:\n{subject_text}"
            f"\n\nBARÈME:\n{rubric.model_dump_json(indent=2)}"
            f"\n\nTRANSCRIPTION:\n{transcription.model_dump_json(indent=2)}"
        )

        response = self.client.messages.create(
            model=settings.claude_model_heavy,
            max_tokens=8192,
            temperature=temperature,
            tools=[_GRADING_TOOL],
            tool_choice={"type": "tool", "name": "save_grading"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                }
            ],
        )

        result = self._extract_tool_result(response, CopyGrade)
        if result.success and result.data is not None and expert_instructions.strip():
            result.data.expert_instructions_used = True
        return result

    # ── Diagnostic ────────────────────────────────────────────────────────────

    @_retry
    def diagnose(self, grades: CopyGrade, curriculum_context: str = "") -> ClaudeResponse:
        logger.info("[%s] Claude diagnostic — modèle : %s",
                    grades.copy_id, settings.claude_model_light)
        base_prompt = self._diagnostic_prompt.replace(
            "{{CURRICULUM_CONTEXT}}", curriculum_context or ""
        )
        prompt = (
            f"{base_prompt}"
            f"\n\nRÉSULTATS DE CORRECTION:\n{grades.model_dump_json(indent=2)}"
        )

        response = self.client.messages.create(
            model=settings.claude_model_light,
            max_tokens=4096,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                },
                {"role": "assistant", "content": "{"},
            ],
        )

        raw = "{" + response.content[0].text
        return self._parse_response(raw, DiagnosticResult)

    # ── Sujet de remédiation ──────────────────────────────────────────────────

    @_retry
    def generate_remediation_subject(self, diagnostic: DiagnosticResult) -> ClaudeResponse:
        """Génère 5 exercices par difficulté identifiée (weaknesses, puis root_causes en fallback)."""
        logger.info("[%s] Claude remédiation — modèle : %s | difficultés : %d",
                    diagnostic.copy_id, settings.claude_model_heavy,
                    len(diagnostic.weaknesses) or len(diagnostic.root_causes))
        if not diagnostic.weaknesses and not diagnostic.root_causes:
            return ClaudeResponse(
                success=False, data=None, confidence=0.0,
                raw_response="",
                error="Aucune difficulté identifiée — pas de sujet de remédiation à générer.",
            )

        n_series = len(diagnostic.weaknesses) or len(diagnostic.root_causes)
        prompt = (
            f"{self._remediation_subject_prompt}"
            f"\n\n---\n\nDIAGNOSTIC ({n_series} difficulté(s) à couvrir):\n"
            f"{diagnostic.model_dump_json(indent=2)}"
        )

        response = self.client.messages.create(
            model=settings.claude_model_heavy,
            max_tokens=8192,   # 35 exercices (~150 tok/exo) = ~5 250 tok — 4096 coupait après la 1re série
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                },
                {"role": "assistant", "content": "{"},
            ],
        )

        raw = "{" + response.content[0].text
        return self._parse_response(raw, RemediationSubject)

    # ── Nom de l'élève depuis la première page ────────────────────────────────

    def extract_student_name(self, first_page: Path) -> str:
        """
        Lit la première page de la copie et retourne le nom complet de l'élève.
        Cherche les champs NOM / PRENOM / NOM ET PRENOM / NAME typiques d'une
        feuille d'examen. Retourne une chaîne vide si rien n'est trouvé.
        Utilise Haiku (tâche simple, coût minimal).
        """
        logger.info("Claude extraction nom — modèle : %s | page : %s",
                    settings.claude_model_light, first_page.name)
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "Regarde cette image de copie d'élève. "
                    "Trouve le nom et le prénom de l'élève (champs NOM, PRENOM, "
                    "NOM ET PRENOM, ou équivalent). "
                    "Retourne UNIQUEMENT le nom complet sous la forme 'Prénom NOM', "
                    "sans aucun autre texte ni ponctuation. "
                    "Si tu ne trouves pas de nom, retourne exactement la chaîne vide."
                ),
            },
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": self._media_type(first_page),
                    "data": self._encode_image(first_page),
                },
            },
        ]
        try:
            response = self.client.messages.create(
                model=settings.claude_model_light,
                max_tokens=64,
                temperature=0,
                messages=[{"role": "user", "content": content}],
            )
            name = response.content[0].text.strip()
            # Rejet si la réponse ressemble à un texte d'échec plutôt qu'un nom
            if len(name) > 80 or "\n" in name:
                return ""
            return name
        except Exception as e:
            logger.warning("extract_student_name échoué : %s", e)
            return ""

    # ── Extraction des questions depuis la transcription ──────────────────────

    @_retry
    def extract_questions_from_transcription(
        self, transcription: TranscriptionResult
    ) -> Rubric:
        """
        Extrait la liste stable des questions depuis la transcription pour créer
        un barème virtuel utilisé quand aucun barème n'est fourni.

        Sépare l'identification des questions du jugement de correction :
        cette passe produit une liste déterministe (tool_use, temperature implicitement
        faible) qui sera passée comme rubric fixe à l'étape de grading.

        Retourne un Rubric vide si aucune question n'est identifiable.
        """
        logger.info(
            "[%s] Extraction des questions depuis la transcription (modèle : %s)…",
            transcription.copy_id, settings.claude_model_heavy,
        )
        content_parts = [
            f"Page {p.page_number} :\n{p.content}"
            for p in transcription.pages
            if p.content.strip() and p.content.strip() != "[ILLISIBLE]"
        ]
        if not content_parts:
            logger.warning(
                "[%s] Transcription vide — impossible d'extraire les questions.",
                transcription.copy_id,
            )
            return Rubric(subject="mathematics", total_points=0, items=[])

        prompt = (
            "Analyse cette transcription de copie d'élève de mathématiques.\n"
            "Identifie TOUTES les questions et sous-questions visibles "
            "(cherche les numéros d'exercices, lettres de sous-questions, etc.).\n"
            "Génère des identifiants courts et cohérents : Q1, Q2a, Q2b, Q3, etc.\n"
            "Ne note pas les réponses — liste uniquement les questions.\n\n"
            "TRANSCRIPTION :\n" + "\n\n".join(content_parts)
        )

        response = self.client.messages.create(
            model=settings.claude_model_heavy,
            max_tokens=1024,
            temperature=0,
            tools=[_QUESTIONS_EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "save_questions"},
            messages=[{"role": "user", "content": prompt}],
        )

        tool_block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )
        if tool_block is None or not isinstance(tool_block.input, dict):
            logger.warning(
                "[%s] Extraction des questions : aucun bloc tool_use reçu.",
                transcription.copy_id,
            )
            return Rubric(subject="mathematics", total_points=0, items=[])

        raw_questions = tool_block.input.get("questions", [])
        items = [
            RubricItem(
                id=q.get("id", f"Q{i + 1}"),
                label=q.get("label", ""),
            )
            for i, q in enumerate(raw_questions)
            if isinstance(q, dict) and q.get("id")
        ]

        logger.warning(
            "[%s] Barème virtuel extrait : %d question(s) — %s",
            transcription.copy_id,
            len(items),
            ", ".join(item.id for item in items[:10]) + ("…" if len(items) > 10 else ""),
        )
        return Rubric(subject="mathematics", total_points=len(items), items=items)

    # ── Énoncé ────────────────────────────────────────────────────────────────

    def extract_subject(self, file_path: Path) -> str:
        images = (
            self._pdf_to_images(file_path)
            if file_path.suffix.lower() == ".pdf"
            else [file_path]
        )
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "Transcris intégralement le texte de cet énoncé. "
                    "Retourne uniquement le texte brut, sans JSON, sans commentaire."
                ),
            },
            *[
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": self._media_type(img),
                        "data": self._encode_image(img),
                    },
                }
                for img in images
            ],
        ]
        response = self.client.messages.create(
            model=settings.claude_model_light,
            max_tokens=2048,
            temperature=0,
            messages=[{"role": "user", "content": content}],
        )
        return response.content[0].text.strip()

    # ── Extraction barème depuis PDF/image ────────────────────────────────────

    @_retry
    def extract_rubric(self, file_path: Path) -> ClaudeResponse:
        """Extrait un barème structuré depuis un PDF ou une image via tool_use."""
        images = (
            self._pdf_to_images(file_path)
            if file_path.suffix.lower() == ".pdf"
            else [file_path]
        )
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "Extrais tous les items de ce barème. "
                    "Pour chaque question ou sous-question, donne son identifiant "
                    "(Q1, Q2a, Q2b, etc.) et son libellé. "
                    "Si le document indique un nombre de points par question, "
                    "utilise-le pour calculer total_points."
                ),
            },
            *[
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": self._media_type(img),
                        "data": self._encode_image(img),
                    },
                }
                for img in images
            ],
        ]

        response = self.client.messages.create(
            model=settings.claude_model_heavy,
            max_tokens=2048,
            temperature=0,
            tools=[_RUBRIC_EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "save_rubric"},
            messages=[{"role": "user", "content": content}],
        )

        raw_resp = self._extract_tool_result(response, _ExtractedRubric)
        if not raw_resp.success or raw_resp.data is None:
            return raw_resp

        extracted: _ExtractedRubric = raw_resp.data
        items = [
            RubricItem(
                id=item.get("id", f"Q{i+1}"),
                label=item.get("label", ""),
                parent_id=item.get("parent_id") or None,
            )
            for i, item in enumerate(extracted.items)
        ]
        total = extracted.total_points or len(items)
        rubric = Rubric(subject="mathematics", total_points=total, items=items)
        return ClaudeResponse(
            success=True,
            data=rubric,
            confidence=raw_resp.confidence,
            raw_response=raw_resp.raw_response,
            error=None,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _media_type(self, path: Path) -> str:
        return _MEDIA_TYPES.get(path.suffix.lower(), "image/jpeg")

    def _encode_image(self, path: Path) -> str:
        import base64
        return base64.b64encode(path.read_bytes()).decode("utf-8")

    def _pdf_to_images(self, pdf_path: Path) -> list[Path]:
        import fitz
        import tempfile
        tmp_dir = Path(tempfile.mkdtemp())
        doc = fitz.open(pdf_path)
        images: list[Path] = []
        for i in range(len(doc)):
            pix = doc.load_page(i).get_pixmap(dpi=150)  # 150 DPI : équilibre qualité/tokens
            img_path = tmp_dir / f"subject_page_{i+1}.jpg"
            pix.save(str(img_path))
            images.append(img_path)
        doc.close()
        return images

    # ── Normalisation des tableaux de strings ─────────────────────────────────

    @staticmethod
    def _item_to_str(item: Any) -> str:
        """Convertit un élément (string ou dict) en string propre.

        Claude retourne parfois des objets {"expression": "...", "interpretation": "..."}
        ou {"zone": "...", "note": "..."} là où le schéma attend une simple string.
        """
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            # Formule : préférer 'expression', sinon 'formula', sinon première valeur
            for key in ("expression", "formula", "formule"):
                if key in item:
                    val = str(item[key])
                    note = item.get("interpretation") or item.get("annotation")
                    return f"{val} ({note})" if note else val
            # Incertitude : préférer 'zone' + 'note'
            for key in ("zone", "area", "location"):
                if key in item:
                    zone = str(item[key])
                    note = item.get("note") or item.get("description") or item.get("issue")
                    return f"{zone} : {note}" if note else zone
            # Schéma : préférer 'description'
            for key in ("description", "desc", "content"):
                if key in item:
                    return str(item[key])
            # Fallback : première valeur non-vide
            for v in item.values():
                if v:
                    return str(v)
        return str(item)

    @classmethod
    def _normalize_transcription(cls, data: Any) -> dict:
        """Normalise le dict issu du tool_use avant validation Pydantic.

        Gère les cas dégénérés :
        - data est une string (JSON partiel non parsé par le SDK)
        - pages[i] est une string au lieu d'un dict
        - formulas/uncertainties[j] est un dict au lieu d'une string
        """
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return {"copy_id": "unknown", "global_quality": "poor", "pages": []}

        if not isinstance(data, dict):
            return {"copy_id": "unknown", "global_quality": "poor", "pages": []}

        raw_pages = data.get("pages", [])
        if not isinstance(raw_pages, list):
            raw_pages = []

        normalized: list[dict] = []
        for i, page in enumerate(raw_pages):
            if isinstance(page, str):
                # Claude a renvoyé la page comme texte brut
                normalized.append({
                    "page_number": i + 1,
                    "content": page,
                    "formulas": [],
                    "diagrams": [],
                    "uncertainties": [],
                    "confidence": 0.5,
                })
            elif isinstance(page, dict):
                # Garantit que content est toujours une chaîne
                if not isinstance(page.get("content"), str):
                    page["content"] = str(page.get("content") or "")
                for field in ("formulas", "diagrams", "uncertainties"):
                    val = page.get(field, [])
                    if not isinstance(val, list):
                        val = [val] if val else []
                    page[field] = [cls._item_to_str(x) for x in val if x is not None]
                normalized.append(page)

        data["pages"] = normalized
        return data

    # ── Extraction tool_use ───────────────────────────────────────────────────

    def _extract_tool_result(self, response: Any, model_cls: type) -> ClaudeResponse:
        """Extrait le résultat d'un appel tool_use — JSON garanti correctement formé."""
        tool_block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )

        if tool_block is None:
            stop = getattr(response, "stop_reason", "?")
            logger.error(
                "Aucun bloc tool_use (stop_reason=%s, model=%s, blocs=%s)",
                stop, model_cls.__name__, [b.type for b in response.content],
            )
            return ClaudeResponse(
                success=False, data=None, confidence=0.0,
                raw_response=str(response.content),
                error=f"Réponse tronquée avant l'appel outil (stop_reason={stop}).",
            )

        # ── Normalise tool_block.input en dict Python ──────────────────────────
        raw = tool_block.input
        raw_repr = repr(raw)[:400]
        logger.debug("tool_block.input type=%s val=%.400s", type(raw).__name__, raw_repr)

        try:
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except json.JSONDecodeError as je:
                    # JSON partiel — tente une réparation basique
                    repaired = _TRAILING_COMMA.sub(r"\1", raw)
                    repaired = _close_json(repaired)
                    try:
                        raw = json.loads(repaired)
                    except json.JSONDecodeError:
                        logger.error("Input outil tronqué irréparable : %s — %.200s", je, raw)
                        return ClaudeResponse(
                            success=False, data=None, confidence=0.0,
                            raw_response=raw,
                            error=f"Input outil JSON invalide : {je}",
                        )

            # Convertit en dict Python quelle que soit la source
            if isinstance(raw, dict):
                data: dict = dict(raw)
            else:
                # Fallback : sérialise/désérialise pour obtenir un dict propre
                try:
                    data = json.loads(json.dumps(raw, default=str))
                    if not isinstance(data, dict):
                        data = {}
                except Exception:
                    data = {}
                logger.warning(
                    "tool_block.input inattendu (type=%s) — converti en dict: %s",
                    type(raw).__name__, str(data)[:200],
                )

            if model_cls is TranscriptionResult:
                data = self._normalize_transcription(data)

            validated = model_cls(**data)
            return ClaudeResponse(
                success=True,
                data=validated,
                confidence=self._estimate_confidence(validated),
                raw_response=str(raw)[:2000],
                error=None,
            )

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(
                "Erreur dans _extract_tool_result (%s) :\n%s\ntool_block.input type=%s val=%.400s",
                model_cls.__name__, tb, type(raw).__name__, raw_repr,
            )
            return ClaudeResponse(
                success=False, data=None, confidence=0.0,
                raw_response=raw_repr,
                error=f"{e} [input_type={type(raw).__name__}]",
            )

    def _parse_response(self, raw_text: str, model_cls: type) -> ClaudeResponse:
        """Parse JSON brut — utilisé uniquement pour diagnose (pas de tool_use)."""
        text = raw_text.strip()

        match = _JSON_FENCE.search(text)
        if match:
            text = match.group(1).strip()
        else:
            open_fence = re.search(r"```(?:json)?\s*([\s\S]+)$", text, re.IGNORECASE)
            if open_fence:
                text = open_fence.group(1).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]

        text = _TRAILING_COMMA.sub(r"\1", text)

        for candidate in (text, _close_json(text)):
            candidate = _TRAILING_COMMA.sub(r"\1", candidate)
            try:
                data = json.loads(candidate)
                validated = model_cls(**data)
                return ClaudeResponse(
                    success=True,
                    data=validated,
                    confidence=self._estimate_confidence(validated),
                    raw_response=raw_text,
                    error=None,
                )
            except (json.JSONDecodeError, Exception):
                continue

        logger.error("JSON irréparable (%s). Début : %.300s", model_cls.__name__, raw_text)
        return ClaudeResponse(
            success=False,
            data=None,
            confidence=0.0,
            raw_response=raw_text,
            error=f"JSON invalide. Début : {raw_text[:200]}",
        )

    def _estimate_confidence(self, result: Any) -> float:
        if hasattr(result, "global_quality"):
            return {"good": 0.9, "medium": 0.7, "poor": 0.5}.get(result.global_quality, 0.5)
        if hasattr(result, "questions"):
            confidences = [q.confidence for q in result.questions if hasattr(q, "confidence")]
            return sum(confidences) / len(confidences) if confidences else 0.5
        return 0.8
