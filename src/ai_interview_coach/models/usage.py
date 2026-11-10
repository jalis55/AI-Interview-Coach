"""Measured token usage without assumed provider prices."""

from pydantic import BaseModel, Field


class UsageSummary(BaseModel):
    provider_calls: int = Field(default=0, ge=0)
    metered_responses: int = Field(default=0, ge=0)
    failed_calls: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    retry_attempts: int = Field(default=0, ge=0)
    fallback_runs: int = Field(default=0, ge=0)
    safe_defaults: int = Field(default=0, ge=0)
    calls_by_stage: dict[str, int] = Field(default_factory=dict)
