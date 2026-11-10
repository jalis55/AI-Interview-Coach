"""Coordinate LLM planning and deterministic fallback."""

from dataclasses import dataclass

from groq import APIConnectionError, APIStatusError, InternalServerError
from langchain_core.exceptions import OutputParserException
from langchain_core.runnables import Runnable

from ai_interview_coach.models.job import JobRequirements
from ai_interview_coach.models.plan import QuestionPlan
from ai_interview_coach.planning.allocation import build_deterministic_plan
from ai_interview_coach.planning.validation import (
    validate_plan_for_requirements,
)
from ai_interview_coach.utils.reliability import run_bounded_attempts


@dataclass(frozen=True)
class PlanningOutcome:
    plan: QuestionPlan
    primary_attempts: int
    used_fallback: bool


def create_coverage_plan(
    requirements: JobRequirements,
    planner: Runnable,
    *,
    max_attempts: int = 3,
) -> PlanningOutcome:
    if not 1 <= max_attempts <= 3:
        raise ValueError("Planner attempts must be between 1 and 3.")

    confirmed = JobRequirements.model_validate(requirements.model_dump())
    attempt_count = 0

    def attempt_plan() -> QuestionPlan:
        nonlocal attempt_count
        attempt_count += 1

        output = planner.invoke({})
        proposed = QuestionPlan.model_validate(output)

        return validate_plan_for_requirements(proposed, confirmed)

    try:
        result = run_bounded_attempts(
            attempt_plan,
            max_attempts=max_attempts,
            retry_on=(
                APIConnectionError,
                InternalServerError,
                OutputParserException,
                ValueError,
            ),
        )
    except APIStatusError:
        # Rejected requests, including rate limits, skip further paid calls.
        pass
    else:
        if result.succeeded:
            assert result.value is not None
            return PlanningOutcome(
                plan=result.value,
                primary_attempts=result.attempts,
                used_fallback=False,
            )

    fallback = build_deterministic_plan(confirmed)
    validated = validate_plan_for_requirements(fallback, confirmed)

    return PlanningOutcome(
        plan=validated,
        primary_attempts=attempt_count,
        used_fallback=True,
    )
