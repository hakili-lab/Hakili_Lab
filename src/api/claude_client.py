import json
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


class ClaudeClient:
    """Client Anthropic pour les tâches de transcription, correction et diagnostic."""

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._transcription_prompt = self._load_prompt("transcription_prompt.md")
        self._grading_prompt = self._load_prompt("grading_prompt.md")
        self._diagnostic_prompt = self._load_prompt("diagnostic_prompt.md")

    def _load_prompt(self, filename: str) -> str:
        """Charge un prompt depuis le dossier prompts/."""
        prompt_path = Path(__file__).parent.parent.parent / "prompts" / filename
        return prompt_path.read_text(encoding="utf-8")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    def transcribe(self, copy_id: str, image_paths: list[Path]) -> ClaudeResponse:
        """Transcrit les images en utilisant Claude Vision."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": self._transcription_prompt},
                    *[
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": self._encode_image(path),
                            },
                        }
                        for path in image_paths
                    ],
                ],
            }
        ]

        response = self.client.messages.create(
            model=settings.claude_model_heavy,
            max_tokens=4096,
            messages=messages,
        )

        return self._parse_response(response.content[0].text, TranscriptionResult)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    def grade(
        self, transcription: TranscriptionResult, rubric: Rubric
    ) -> ClaudeResponse:
        """Corrige la copie selon le barème."""
        prompt = f"{self._grading_prompt}\n\nÉNONCÉ:\n{transcription}\n\nBARÈME:\n{rubric}"

        response = self.client.messages.create(
            model=settings.claude_model_light,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        return self._parse_response(response.content[0].text, CopyGrade)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    def diagnose(self, grades: CopyGrade) -> ClaudeResponse:
        """Produit le diagnostic pédagogique."""
        prompt = f"{self._diagnostic_prompt}\n\nRÉSULTATS DE CORRECTION:\n{grades}"

        response = self.client.messages.create(
            model=settings.claude_model_light,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        return self._parse_response(response.content[0].text, DiagnosticResult)

    def _encode_image(self, path: Path) -> str:
        """Encode une image en base64."""
        import base64

        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _parse_response(self, raw_text: str, model_cls: type) -> ClaudeResponse:
        """Parse la réponse JSON et valide avec Pydantic."""
        try:
            data = json.loads(raw_text)
            validated = model_cls(**data)
            confidence = self._estimate_confidence(validated)
            return ClaudeResponse(
                success=True,
                data=validated,
                confidence=confidence,
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
        """Estime la confiance basée sur les données du résultat."""
        if hasattr(result, "global_quality"):
            quality_map = {"good": 0.9, "medium": 0.7, "poor": 0.5}
            return quality_map.get(result.global_quality, 0.5)

        if hasattr(result, "questions"):
            confidences = [q.confidence for q in result.questions if hasattr(q, "confidence")]
            return sum(confidences) / len(confidences) if confidences else 0.5

        return 0.8  # Default high confidence