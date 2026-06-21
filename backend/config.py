from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    gemini_api_key: str = ""
    numbeo_api_key: str = ""
    bls_api_key: str = ""
    cors_origins: list[str] = ["http://localhost:5173"]
    environment: str = "dev"

    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8")


settings = Settings()
