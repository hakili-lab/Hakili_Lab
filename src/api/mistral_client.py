"""
Clients Mistral pour Hakili Lab :
  - MistralTranscriptionClient  : transcription vision via Pixtral (pixtral-12b-2409)
  - MistralRemediationClient    : remédiation via Mistral Small (français académique natif)

Coûts Mistral (juin 2026) :
  Pixtral 12B        : $0.15/$0.15 par million de tokens
  Mistral Small 3.1  : $0.10/$0.30 par million de tokens
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re
from pathlib import Path
from typing import Any

from mistralai import Mistral
from PIL import Image
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.models.domain import (
    ClaudeResponse,
    CopyGrade,
    DiagnosticResult,
    PageTranscription,
    RemediationSubject,
    TranscriptionResult,
)

logger = logging.getLogger(__name__)

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")
_MAX_PAGES_PER_BATCH = 3


# ── Utilitaires JSON ──────────────────────────────────────────────────────────

def _repair_json(text: str) -> str:
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
    close_map = {"[": "]", "{": "}"}
    return text + "".join(close_map[c] for c in reversed(stack))


def _item_to_str(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("expression", "formula", "formule"):
            if key in item:
                val = str(item[key])
                note = item.get("interpretation") or item.get("annotation")
                return f"{val} ({note})" if note else val
        for key in ("zone", "area", "location"):
            if key in item:
                zone = str(item[key])
                note = item.get("note") or item.get("description") or item.get("issue")
                return f"{zone} : {note}" if note else zone
        for key in ("description", "desc", "content"):
            if key in item:
                return str(item[key])
        for v in item.values():
            if v:
                return str(v)
    return str(item)


def _normalize_transcription(data: Any) -> dict:
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return {"copy_id": "unknown", "global_quality": "poor", "pages": []}
    if not isinstance(data, dict):
        return {"copy_id": "unknown", "global_quality": "poor", "pages": []}
    if "global_quality" not in data or data["global_quality"] not in ("good", "medium", "poor"):
        data["global_quality"] = "medium"
    data["copy_id"] = str(data["copy_id"]) if "copy_id" in data else "unknown"

    raw_pages = data.get("pages", [])
    if not isinstance(raw_pages, list):
        raw_pages = []
    normalized: list[dict] = []
    for i, page in enumerate(raw_pages):
        if isinstance(page, str):
            normalized.append({
                "page_number": i + 1,
                "content": page,
                "formulas": [],
                "diagrams": [],
                "uncertainties": [],
                "confidence": 0.5,
            })
        elif isinstance(page, dict):
            if not isinstance(page.get("content"), str):
                page["content"] = str(page.get("content") or "")
            for field in ("formulas", "diagrams", "uncertainties"):
                val = page.get(field, [])
                if not isinstance(val, list):
                    val = [val] if val else []
                page[field] = [_item_to_str(x) for x in val if x is not None]
            normalized.append(page)
    data["pages"] = normalized
    return data


def _parse_json_response(raw: str, model_cls: type) -> ClaudeResponse:
    text = raw.strip()
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    text = _TRAILING_COMMA.sub(r"\1", text)

    for candidate in (text, _repair_json(text)):
        candidate = _TRAILING_COMMA.sub(r"\1", candidate)
        try:
            data = json.loads(candidate)
            validated = model_cls(**data)
            return ClaudeResponse(
                success=True, data=validated, confidence=0.88,
                raw_response=raw[:2000], error=None,
            )
        except (json.JSONDecodeError, Exception):
            continue

    logger.error("Mistral — JSON irréparable (%s). Début : %.300s", model_cls.__name__, raw)
    return ClaudeResponse(
        success=False, data=None, confidence=0.0,
        raw_response=raw[:500],
        error=f"JSON invalide retourné par Mistral. Début : {raw[:200]}",
    )


def _load_prompt(filename: str) -> str:
    prompt_path = Path(__file__).parent.parent.parent / "prompts" / filename
    return prompt_path.read_text(encoding="utf-8")


# ── Retry ─────────────────────────────────────────────────────────────────────

def _is_retryable_mistral(exc: BaseException) -> bool:
    # Mistral SDK lève des HTTPStatusError (httpx) pour 429/500
    name = type(exc).__name__
    return "RateLimit" in name or "Timeout" in name or "Connection" in name


_retry = retry(
    retry=retry_if_exception(_is_retryable_mistral),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    reraise=True,
)


# ══════════════════════════════════════════════════════════════════════════════
# Client transcription (Pixtral)
# ══════════════════════════════════════════════════════════════════════════════

def _is_retryable_mistral_vision(exc: BaseException) -> bool:
    name = type(exc).__name__
    return "RateLimit" in name or "Timeout" in name or "Connection" in name or "429" in str(exc)


_retry_vision = retry(
    retry=retry_if_exception(_is_retryable_mistral_vision),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    reraise=True,
)


class MistralTranscriptionClient:
    """Transcription multimodale via Pixtral — remplace ClaudeClient.transcribe()."""

    def __init__(self) -> None:
        if not settings.mistral_api_key:
            raise ValueError(
                "MISTRAL_API_KEY manquante. Ajoutez-la dans .env pour utiliser Mistral vision."
            )
        self._client = Mistral(api_key=settings.mistral_api_key)
        self._transcription_prompt = _load_prompt("transcription_prompt.md")
        logger.info("MistralTranscriptionClient initialisé (modèle=%s)", settings.mistral_vision_model)

    def transcribe(self, copy_id: str, image_paths: list[Path]) -> ClaudeResponse:
        try:
            if len(image_paths) <= _MAX_PAGES_PER_BATCH:
                return self._transcribe_batch(copy_id, image_paths, page_offset=0)
            return self._transcribe_batched(copy_id, image_paths)
        except Exception as e:
            logger.error("Mistral transcription abandonnée (copy_id=%s) : %s", copy_id, e)
            return ClaudeResponse(
                success=False, data=None, confidence=0.0, raw_response="", error=str(e),
            )

    def _transcribe_batched(self, copy_id: str, image_paths: list[Path]) -> ClaudeResponse:
        all_pages: list[PageTranscription] = []
        qualities: list[str] = []
        for start in range(0, len(image_paths), _MAX_PAGES_PER_BATCH):
            batch = image_paths[start:start + _MAX_PAGES_PER_BATCH]
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
        merged = TranscriptionResult(copy_id=copy_id, global_quality=global_quality, pages=all_pages)  # type: ignore[arg-type]
        avg_conf = sum(p.confidence for p in all_pages) / len(all_pages) if all_pages else 0.5
        return ClaudeResponse(
            success=True, data=merged, confidence=avg_conf,
            raw_response=f"[mistral batched {len(all_pages)} pages]", error=None,
        )

    @_retry_vision
    def _transcribe_batch(
        self, copy_id: str, image_paths: list[Path], page_offset: int = 0
    ) -> ClaudeResponse:
        page_hint = (
            f"\nCes images sont les pages {page_offset + 1} à {page_offset + len(image_paths)}."
            f" Utilise page_number à partir de {page_offset + 1}."
            if page_offset > 0 else ""
        )
        prompt = (
            f"{self._transcription_prompt}\n\ncopy_id : {copy_id}{page_hint}\n\n"
            "Retourne UNIQUEMENT un objet JSON valide sans aucune balise markdown."
        )

        content: list[dict] = [{"type": "text", "text": prompt}]
        for path in image_paths:
            img = Image.open(path).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })

        try:
            response = self._client.chat.complete(
                model=settings.mistral_vision_model,
                messages=[{"role": "user", "content": content}],
                temperature=0.1,
                max_tokens=4096,
            )
            raw = (response.choices[0].message.content or "").strip()

            m = _JSON_FENCE.search(raw)
            if m:
                raw = m.group(1).strip()
            start_idx = raw.find("{")
            end_idx = raw.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                raw = raw[start_idx:end_idx + 1]
            raw = _TRAILING_COMMA.sub(r"\1", raw)

            data_dict: dict | None = None
            for candidate in (raw, _repair_json(raw)):
                candidate = _TRAILING_COMMA.sub(r"\1", candidate)
                try:
                    data_dict = json.loads(candidate)
                    break
                except json.JSONDecodeError:
                    continue

            if data_dict is None:
                logger.error(
                    "Mistral vision — JSON irréparable (copy_id=%s, offset=%d). Début : %.300s",
                    copy_id, page_offset, raw,
                )
                return ClaudeResponse(
                    success=False, data=None, confidence=0.0,
                    raw_response=raw[:500], error="JSON invalide retourné par Mistral vision.",
                )

            data_dict = _normalize_transcription(data_dict)
            validated = TranscriptionResult(**data_dict)
            logger.info(
                "Mistral vision OK (copy_id=%s, pages=%d-%d, qualité=%s)",
                copy_id, page_offset + 1, page_offset + len(image_paths), validated.global_quality,
            )
            return ClaudeResponse(
                success=True, data=validated,
                confidence={"good": 0.9, "medium": 0.7, "poor": 0.5}.get(validated.global_quality, 0.5),
                raw_response=raw[:2000], error=None,
            )

        except Exception as e:
            if _is_retryable_mistral_vision(e):
                logger.warning("Mistral vision 429 (copy_id=%s, offset=%d) — retry : %s", copy_id, page_offset, e)
                raise
            logger.error("Erreur Mistral vision (copy_id=%s, offset=%d) : %s", copy_id, page_offset, e)
            return ClaudeResponse(success=False, data=None, confidence=0.0, raw_response="", error=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# Client remédiation (Mistral Small)
# ══════════════════════════════════════════════════════════════════════════════

_DIAGNOSTIC_SCHEMA = """
{
  "copy_id": "<string>",
  "strengths": ["<string>", ...],
  "weaknesses": ["<string>", ...],
  "root_causes": [
    {
      "visible_error": "<string>",
      "hidden_cause": "<string>",
      "linked_questions": ["Q1", "Q3", ...]
    }
  ],
  "skills": [
    {
      "name": "<string>",
      "level": "<mastered|partial|weak|unknown>",
      "evidence": "<string>"
    }
  ],
  "remediation_plan": [
    {
      "priority": <integer>,
      "topic": "<string>",
      "action": "<string>"
    }
  ]
}
"""


class MistralRemediationClient:
    """Diagnostic pédagogique et génération d'exercices de remédiation via Mistral Small."""

    def __init__(self) -> None:
        if not settings.mistral_api_key:
            raise ValueError(
                "MISTRAL_API_KEY manquante. Ajoutez-la dans .env pour utiliser Mistral."
            )
        self._client = Mistral(api_key=settings.mistral_api_key)
        self._remediation_prompt = _load_prompt("remediation_subject_prompt.md")
        self._diagnostic_prompt = _load_prompt("diagnostic_prompt.md")
        logger.info("MistralRemediationClient initialisé (modèle=%s)", settings.mistral_model)

    @_retry
    def diagnose(self, grades: CopyGrade, curriculum_context: str = "") -> ClaudeResponse:
        """Diagnostic pédagogique via Mistral Small — français académique natif."""
        logger.info("[%s] Mistral diagnostic — modèle : %s", grades.copy_id, settings.mistral_model)
        base_prompt = self._diagnostic_prompt.replace(
            "{{CURRICULUM_CONTEXT}}", curriculum_context or ""
        )
        user_content = (
            f"{base_prompt}"
            f"\n\nRÉSULTATS DE CORRECTION:\n{grades.model_dump_json(indent=2)}"
            f"\n\nRetourne UNIQUEMENT un objet JSON valide avec cette structure exacte :"
            f"\n{_DIAGNOSTIC_SCHEMA}"
        )
        try:
            response = self._client.chat.complete(
                model=settings.mistral_model,
                messages=[{"role": "user", "content": user_content}],
                response_format={"type": "json_object"},
                max_tokens=4096,
                temperature=0.1,
            )
            raw = response.choices[0].message.content or ""
            logger.info(
                "Mistral diagnostic OK — tokens: %d in / %d out",
                response.usage.prompt_tokens, response.usage.completion_tokens,
            )
            return _parse_json_response(raw, DiagnosticResult)
        except Exception as e:
            logger.error("Mistral diagnose erreur : %s", e)
            return ClaudeResponse(success=False, data=None, confidence=0.0,
                                  raw_response="", error=str(e))

    @_retry
    def generate_remediation_subject(self, diagnostic: DiagnosticResult) -> ClaudeResponse:
        """
        Génère 5 exercices progressifs par difficulté identifiée.

        Mistral Small 3.1 — français académique natif, terminologie CEDEAO/UEMOA.
        """
        logger.info("[%s] Mistral remédiation — modèle : %s | difficultés : %d",
                    diagnostic.copy_id, settings.mistral_model,
                    len(diagnostic.weaknesses) or len(diagnostic.root_causes))
        if not diagnostic.weaknesses and not diagnostic.root_causes:
            return ClaudeResponse(
                success=False, data=None, confidence=0.0,
                raw_response="",
                error="Aucune difficulté identifiée — pas de sujet de remédiation à générer.",
            )

        n_series = len(diagnostic.weaknesses) or len(diagnostic.root_causes)
        user_content = (
            f"{self._remediation_prompt}"
            f"\n\n---\n\nDIAGNOSTIC ({n_series} difficulté(s) à couvrir):\n"
            f"{diagnostic.model_dump_json(indent=2)}"
        )

        try:
            response = self._client.chat.complete(
                model=settings.mistral_model,
                messages=[{"role": "user", "content": user_content}],
                response_format={"type": "json_object"},
                max_tokens=8192,
                temperature=0.4,   # Légère créativité pour varier les exercices
            )
            raw = response.choices[0].message.content or ""
            logger.info(
                "Mistral remédiation OK — tokens: %d in / %d out",
                response.usage.prompt_tokens, response.usage.completion_tokens,
            )
            return _parse_json_response(raw, RemediationSubject)
        except Exception as e:
            logger.error("Mistral generate_remediation_subject erreur : %s", e)
            return ClaudeResponse(success=False, data=None, confidence=0.0,
                                  raw_response="", error=str(e))
