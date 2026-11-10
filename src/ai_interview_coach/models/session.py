"""Interview lifecycle states."""

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from ai_interview_coach.models.activity import ActivityEvent
from ai_interview_coach.models.interview import InterviewProgress, PendingEvaluation
from ai_interview_coach.models.job import JobRequirements, Seniority
from ai_interview_coach.models.plan import QuestionPlan
from ai_interview_coach.models.question import InterviewQuestion
from ai_interview_coach.models.report import InterviewReport
from ai_interview_coach.models.research import SearchOutcome
from ai_interview_coach.models.usage import UsageSummary


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

    jd_context: str = ""
    plan: QuestionPlan | None = None
    plan_used_fallback: bool = False
    planning_attempts: int = Field(default=0, ge=0)
    search_cache: dict[tuple[str, Seniority], SearchOutcome] = Field(
        default_factory=dict,
    )
    search_calls_by_skill: dict[str, int] = Field(
        default_factory=dict,
    )
    candidate_pool: list[InterviewQuestion] = Field(default_factory=list)
    asked_questions: list[str] = Field(default_factory=list)
    activity_log: list[ActivityEvent] = Field(default_factory=list)
    research_complete: bool = False
    jd_id: UUID = Field(default_factory=uuid4)
    lineage_id: UUID = Field(default_factory=uuid4)
    progress: InterviewProgress = Field(default_factory=InterviewProgress)
    final_report: InterviewReport | None = None
    report_history: list[InterviewReport] = Field(default_factory=list)
    usage: UsageSummary = Field(default_factory=UsageSummary)
    is_demo: bool = False
    pending_evaluations: dict[UUID, PendingEvaluation] = Field(default_factory=dict)
