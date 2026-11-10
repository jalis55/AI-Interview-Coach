"""Load and validate application configuration."""

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    groq_api_key: SecretStr
    tavily_api_key: SecretStr
    groq_model: str = Field(min_length=1)

    request_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    primary_max_attempts: int = Field(default=3, ge=1, le=3)
    fallback_max_attempts: int = Field(default=2, ge=1, le=2)
    search_domains: list[str] = Field(
        default_factory=lambda: ["geeksforgeeks.org", "interviewbit.com", "stackoverflow.com"]
    )
    candidates_per_skill: int = Field(default=6, ge=3, le=9)
    candidate_pool_limit: int = Field(default=90, ge=30, le=120)
    tool_loop_max_iterations: int = Field(default=3, ge=1, le=3)

    @field_validator("groq_api_key", "tavily_api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr) -> SecretStr:
        cleaned = value.get_secret_value().strip()
        if not cleaned:
            raise ValueError("API key must not be empty.")
        return SecretStr(cleaned)

    @field_validator("groq_model", mode="before")
    @classmethod
    def normalize_model_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
