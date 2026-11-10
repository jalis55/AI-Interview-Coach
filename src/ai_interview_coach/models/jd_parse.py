"""Validated outcomes for job-description parsing."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_interview_coach.models.job import JobRequirements


class JDParseResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    status: Literal["valid", "needs_correction"]
    requirements: JobRequirements | None
    message: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_outcome(self) -> "JDParseResult":
        if self.status == "valid" and self.requirements is None:
            raise ValueError("A valid result must include job requirements.")

        if self.status == "needs_correction" and self.requirements is not None:
            raise ValueError("A correction result must not include job requirements.")

        return self
