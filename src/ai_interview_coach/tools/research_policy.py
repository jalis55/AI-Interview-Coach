"""Application-owned authorization for question research."""

from ai_interview_coach.models.job import JobRequirements
from ai_interview_coach.models.plan import QuestionPlan
from ai_interview_coach.models.research import QuestionResearchRequest
from ai_interview_coach.planning.validation import (
    validate_plan_for_requirements,
)


class ResearchAuthorizationError(ValueError):
    """Raised when research targets an unauthorized skill."""


def authorize_research_request(
    request: QuestionResearchRequest,
    *,
    requirements: JobRequirements,
    plan: QuestionPlan,
) -> str:
    validated_plan = validate_plan_for_requirements(plan, requirements)

    if request.skill not in validated_plan.prioritized_skills:
        raise ResearchAuthorizationError(
            "Research is allowed only for core skills selected in the plan."
        )

    return request.skill
