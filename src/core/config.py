from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Anthropic Claude
    anthropic_api_key: str
    claude_model_heavy: str = "claude-opus-4-7"
    claude_model_light: str = "claude-haiku-4-5-20251001"

    # Seuils pipeline
    confidence_review_threshold: float = 0.75
    image_min_resolution: int = 1000
    image_blur_threshold: float = 100.0

    # Stockage
    runs_dir: str = "./runs"
    subject: str = "mathematics"


settings = Settings()
