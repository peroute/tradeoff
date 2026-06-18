from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str = ""
    numbeo_api_key: str = ""
    bls_api_key: str = ""
    cors_origins: list[str] = ["http://localhost:5173"]
    environment: str = "dev"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
