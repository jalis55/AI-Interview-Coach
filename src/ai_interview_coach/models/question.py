"""Validated interview questions and their provenance."""

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from ai_interview_coach.models.plan import Difficulty


class QuestionSource(StrEnum):
    WEB = "web"
    LLM_FALLBACK = "llm_fallback"


class InterviewQuestion(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    id: UUID = Field(default_factory=uuid4)
    question: str = Field(min_length=1, max_length=1500)
    skill: str = Field(min_length=1, max_length=200)
    difficulty: Difficulty
    source: QuestionSource
    rationale: str = Field(min_length=1, max_length=800)
    source_url: HttpUrl | None = None
    source_title: str | None = None

    @model_validator(mode="after")
    def validate_provenance(self) -> "InterviewQuestion":
        if self.source == QuestionSource.WEB and self.source_url is None:
            raise ValueError("Web questions must include a source URL.")

        return self


class QuestionBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[InterviewQuestion] = Field(max_length=12)
