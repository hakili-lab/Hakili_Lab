import json
import re
from pathlib import Path
from typing import Any

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.models.domain import (
    ClaudeResponse,
    CopyGrade,
    DiagnosticResult,
    Rubric,
    TranscriptionResult,
)

_MEDIA_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


class ClaudeClient:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._transcription_prompt = self._load_prompt("transcription_prompt.md")
        self._grading_prompt = self._load_prompt("grading_prompt.md")
        self._diagnostic_prompt = self._load_prompt("diagnostic_prompt.md")

    def _load_prompt(self, filename: str) -> str:
        prompt_path = Path(__file__).parent.parent.parent / "prompts" / filename
        return prompt_path.read_text(encoding="utf-8")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), reraise=True)
    def transcribe(self, copy_id: str, image_paths: list[Path]) -> ClaudeResponse:
        """Transcrit les images en utilisant Claude Vision avec prompt caching."""
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": self._transcription_prompt,
                "cache_control": {"type": "ephemeral"},  # prompt statique → cache
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
            max_tokens=4096,
            messages=[{"role": "user", "content": content}],
        )

        return self._parse_response(response.content[0].text, TranscriptionResult)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), reraise=True)
    def grade(
        self,
        transcription: TranscriptionResult,
        rubric: Rubric,
        subject_text: str,
        expert_instructions: str = "",
    ) -> ClaudeResponse:
        """Corrige la copie selon le barème. Injecte l'énoncé et les instructions expert."""
        expert_block = f"\n\nINSTRUCTIONS EXPERT:\n{expert_instructions}" if expert_instructions.strip() else ""

        prompt = (
            f"{self._grading_prompt}{expert_block}"
            f"\n\nÉNONCÉ:\n{subject_text}"
            f"\n\nBARÈME:\n{rubric.model_dump_json(indent=2)}"
            f"\n\nTRANSCRIPTION:\n{transcription.model_dump_json(indent=2)}"
        )

        response = self.client.messages.create(
            model=settings.claude_model_heavy,
            max_tokens=2048,
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

        result = self._parse_response(response.content[0].text, CopyGrade)
        if result.success and result.data is not None and expert_instructions.strip():
            result.data.expert_instructions_used = True
        return result

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), reraise=True)
    def diagnose(self, grades: CopyGrade) -> ClaudeResponse:
        """Produit le diagnostic pédagogique."""
        prompt = (
            f"{self._diagnostic_prompt}"
            f"\n\nRÉSULTATS DE CORRECTION:\n{grades.model_dump_json(indent=2)}"
        )

        response = self.client.messages.create(
            model=settings.claude_model_light,
            max_tokens=2048,
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

        return self._parse_response(response.content[0].text, DiagnosticResult)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _media_type(self, path: Path) -> str:
        return _MEDIA_TYPES.get(path.suffix.lower(), "image/jpeg")

    def _encode_image(self, path: Path) -> str:
        import base64
        return base64.b64encode(path.read_bytes()).decode("utf-8")

    def _parse_response(self, raw_text: str, model_cls: type) -> ClaudeResponse:
        """Parse la réponse JSON — gère les blocs markdown ```json ... ```."""
        text = raw_text.strip()
        match = _JSON_FENCE.search(text)
        if match:
            text = match.group(1).strip()

        try:
            data = json.loads(text)
            validated = model_cls(**data)
            return ClaudeResponse(
                success=True,
                data=validated,
                confidence=self._estimate_confidence(validated),
                raw_response=raw_text,
                error=None,
            )
        except Exception as e:
            return ClaudeResponse(
                success=False,
                data=None,
                confidence=0.0,
                raw_response=raw_text,
                error=str(e),
            )

    def _estimate_confidence(self, result: Any) -> float:
        if hasattr(result, "global_quality"):
            return {"good": 0.9, "medium": 0.7, "poor": 0.5}.get(result.global_quality, 0.5)
        if hasattr(result, "questions"):
            confidences = [q.confidence for q in result.questions if hasattr(q, "confidence")]
            return sum(confidences) / len(confidences) if confidences else 0.5
        return 0.8
