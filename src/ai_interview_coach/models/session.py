"""Interview lifecycle states."""

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from ai_interview_coach.models.job import JobRequirements


class InterviewStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    PREPARING = "preparing"
    AWAITING_ANSWER = "awaiting_answer"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    RECOVERABLE_ERROR = "recoverable_error"


class InterviewSession(BaseModel):
    """Application-owned state for one interview."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    session_id: UUID = Field(default_factory=uuid4)
    status: InterviewStatus = InterviewStatus.DRAFT
    requirements: JobRequirements | None = None
