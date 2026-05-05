from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    app_env: str = os.getenv("APP_ENV", "development")
    data_dir: str = os.getenv("DATA_DIR", "./runs")
    ai_provider: str = os.getenv("AI_PROVIDER", "anthropic")

settings = Settings()
