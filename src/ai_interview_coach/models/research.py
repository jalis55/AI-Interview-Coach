"""Validated arguments for interview-question research."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class QuestionResearchRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    skill: str = Field(min_length=1, max_length=200)

    @field_validator("skill")
    @classmethod
    def normalize_skill(cls, value: str) -> str:
        return " ".join(value.split()).casefold()


class SearchStatus(StrEnum):
    SUCCESS = "success"
    EMPTY = "empty"
    ERROR = "error"


class SearchSnippet(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    title: str = Field(min_length=1, max_length=500)
    url: HttpUrl
    content: str = Field(min_length=1, max_length=4_000)


class SearchOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SearchStatus
    http_status: int | None = Field(default=None, ge=100, le=599)
    error_category: (
        Literal["http_error", "timeout", "connection_error", "invalid_response", "search_error"]
        | None
    ) = None
    snippets: list[SearchSnippet] = Field(
        default_factory=list,
        max_length=8,
    )

    @model_validator(mode="after")
    def validate_outcome(self) -> "SearchOutcome":
        if self.status == SearchStatus.SUCCESS and not self.snippets:
            raise ValueError("Successful search must contain snippets.")

        if self.status != SearchStatus.SUCCESS and self.snippets:
            raise ValueError("Empty or failed search must not contain snippets.")

        return self
