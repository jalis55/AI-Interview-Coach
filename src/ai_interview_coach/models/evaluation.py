"""Validated feedback for a candidate's answer."""

from pydantic import BaseModel, ConfigDict, Field


class AnswerScore(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    score: int = Field(strict=True, ge=1, le=10)
    feedback: str = Field(min_length=1)
    strengths: list[str]
    improvements: list[str]
