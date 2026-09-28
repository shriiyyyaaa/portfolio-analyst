"""
Centralized app configuration.

Everything that varies between your machine, a teammate's machine, and a
deployed server lives here - never hardcoded elsewhere in the codebase.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openrouter_api_key: str = ""
    default_model: str = "anthropic/claude-3.5-sonnet"
    database_url: str = "sqlite:///./portfolio.db"
    admin_password: str = ""
    fallback_model: str = ""   # optional: tried if the primary model fails twice
    cors_origins: str = "*"    # comma-separated allowed origins; set to the frontend URL in production


# Import this singleton everywhere instead of re-reading the .env file.
settings = Settings()
