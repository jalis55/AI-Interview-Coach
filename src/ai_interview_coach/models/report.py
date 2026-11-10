"""Evidence-aware reports; numeric summaries are application calculated."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ai_interview_coach.models.plan import Difficulty


class ReportText(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=4000)


class Recommendations(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[str] = Field(min_length=1, max_length=10)


class ObservedScore(BaseModel):
    difficulty: Difficulty
    score: int = Field(strict=True, ge=1, le=10)
    status: Literal["valid", "defaulted"]


class SkillEvidence(BaseModel):
    skill: str
    target_difficulty: Difficulty
    observations: list[ObservedScore]
    valid_count: int = Field(ge=0)
    reliable_mean: float | None = Field(default=None, ge=1, le=10)
    assessment: Literal["insufficiently_assessed", "observed_practice"]
    target_gap: str


class InterviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strengths_summary: str
    gaps_summary: str
    recommendations: list[str]
    overall_score: float = Field(ge=1, le=10)
    defaulted_count: int = Field(ge=0)
    evaluated_count: int = Field(ge=1)
    readiness_status: Literal["unavailable", "limited_evidence"]
    coverage: list[SkillEvidence]
    omitted_skills: list[str]
    caveat: str
