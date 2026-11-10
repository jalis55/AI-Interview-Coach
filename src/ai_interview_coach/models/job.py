"""Validated requirements extracted from a job description."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Seniority(StrEnum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"


class JobRequirements(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    role: str = Field(min_length=1)
    seniority: Seniority
    core_skills: list[str] = Field(min_length=1)
    nice_to_have: list[str] = Field(default_factory=list)

    @field_validator("core_skills", "nice_to_have")
    @classmethod
    def normalize_skills(cls, skills: list[str]) -> list[str]:
        normalized = []
        seen = set()

        for skill in skills:
            cleaned = " ".join(skill.split()).casefold()

            if not cleaned:
                raise ValueError("Skill names must not be blank.")

            if cleaned not in seen:
                normalized.append(cleaned)
                seen.add(cleaned)

        return normalized
