"""Application settings.

All configuration comes from environment variables (and a local, gitignored `.env` file in development).
Each variable name is the upper-cased field name: `log_level` is read from `LOG_LEVEL`.
Read settings through `get_settings()` so they are parsed once and can be overridden in tests.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]
AuthMode = Literal["dev", "jwks"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Environment = "local"
    app_name: str = "Creator API"
    app_version: str = "0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description='Browser origins allowed to call the API. In .env, write it as JSON: ["https://app.example.com"]',
    )
    database_url: str = Field(
        default="postgresql+asyncpg://tailor:tailor@localhost:5433/tailor",
        description="SQLAlchemy async URL. The default matches docker-compose.yml.",
    )
    database_echo: bool = Field(default=False, description="Log every SQL statement (debugging only).")

    # --- LLM (Groq; see app/llm/) ---
    groq_api_key: SecretStr | None = Field(default=None, description="Developer-tier key. Without it, AI routes return 503.")
    llm_run_budget_usd: float = Field(default=0.5, description="Spend cap per request that calls the LLM.")
    llm_max_concurrency: int = Field(default=8, description="Max simultaneous Groq requests per API process.")

    # --- Sign-in tokens (see app/core/auth.py) ---
    auth_mode: AuthMode = Field(
        default="dev",
        description="'dev': tokens signed with AUTH_DEV_SECRET (local/test only). "
        "'jwks': tokens from the real sign-in provider, checked against its public keys.",
    )
    auth_dev_secret: SecretStr = SecretStr("local-dev-secret-not-for-production-use-0001")
    auth_jwks_url: str | None = Field(default=None, description="Where the provider publishes its public keys.")
    auth_issuer: str | None = Field(default=None, description="Expected `iss` claim (who issued the token).")
    auth_audience: str = Field(default="tailor-api", description="Expected `aud` claim (who the token is for).")

    @model_validator(mode="after")
    def _check_auth(self) -> Settings:
        if self.auth_mode == "dev" and self.environment in ("staging", "production"):
            raise ValueError("AUTH_MODE=dev is only allowed in local and test environments")
        if self.auth_mode == "jwks" and not (self.auth_jwks_url and self.auth_issuer):
            raise ValueError("AUTH_MODE=jwks needs AUTH_JWKS_URL and AUTH_ISSUER")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def json_logs(self) -> bool:
        """Machine-readable logs everywhere except on a developer's machine."""
        return self.environment != "local"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
