"""Turn ledger and evidence contracts for coverage and practice rounds."""

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_interview_coach.models.evaluation import AnswerScore
from ai_interview_coach.models.plan import Difficulty, QuestionSlot
from ai_interview_coach.models.question import InterviewQuestion


class EvaluationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["accepted", "unrelated"]
    assessment: AnswerScore | None

    @model_validator(mode="after")
    def validate_decision(self):
        if (self.status == "accepted") != (self.assessment is not None):
            raise ValueError("Only accepted answers must contain an assessment.")
        return self


class EvaluationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turn_id: UUID
    round_id: UUID
    question: InterviewQuestion
    answer: str = Field(min_length=1, max_length=12000)
    assessment: AnswerScore
    evaluation_status: Literal["valid", "defaulted"]
    primary_attempts: int = Field(ge=0, le=3)
    fallback_attempts: int = Field(ge=0, le=2)


class InterviewProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")
    round_id: UUID = Field(default_factory=uuid4)
    round_kind: Literal["coverage", "practice"] = "coverage"
    round_slots: list[QuestionSlot] = Field(default_factory=list, max_length=10)
    current_index: int = Field(default=0, ge=0)
    current_question: InterviewQuestion | None = None
    current_turn_id: UUID | None = None
    records: list[EvaluationRecord] = Field(default_factory=list)
    processed_turn_ids: set[UUID] = Field(default_factory=set)
    covered_skills: set[str] = Field(default_factory=set)
    practice_difficulty: dict[str, Difficulty] = Field(default_factory=dict)
    target_difficulty: dict[str, Difficulty] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_progress(self):
        if self.current_index > len(self.round_slots):
            raise ValueError("Progress exceeds round size.")
        if (self.current_question is None) != (self.current_turn_id is None):
            raise ValueError("Current question and turn ID must be set together.")
        ids = [record.turn_id for record in self.records]
        if len(ids) != len(set(ids)) or set(ids) != self.processed_turn_ids:
            raise ValueError("Evaluation records and processed turn IDs must agree.")
        return self


class EvaluationOutcome(BaseModel):
    decision: EvaluationDecision
    defaulted: bool
    primary_attempts: int
    fallback_attempts: int


class PendingEvaluation(BaseModel):
    answer: str
    outcome: EvaluationOutcome
