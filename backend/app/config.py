
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openrouter_api_key: str = ""
    default_model: str = "anthropic/claude-3.5-sonnet"
    database_url: str = "sqlite:///./portfolio.db"
    admin_password: str = ""
    fallback_model: str = ""   
    cors_origins: str = "*"    



settings = Settings()
