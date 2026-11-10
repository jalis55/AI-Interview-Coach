"""Planning service tests using fake runnables."""

import httpx
import pytest
from groq import AuthenticationError, RateLimitError
from langchain_core.runnables import RunnableLambda

from ai_interview_coach.models.job import JobRequirements
from ai_interview_coach.planning.allocation import build_deterministic_plan
from ai_interview_coach.services.planning import create_coverage_plan


@pytest.fixture
def requirements():
    return JobRequirements(
        role="Backend Engineer",
        seniority="mid",
        core_skills=["python", "sql"],
    )


def fake_planner(outputs):
    pending = iter(outputs)
    calls = []

    def invoke(inputs):
        calls.append(inputs)
        return next(pending)

    return RunnableLambda(invoke), calls


def test_accepts_valid_plan(requirements):
    proposed = build_deterministic_plan(requirements)
    planner, calls = fake_planner([proposed])

    outcome = create_coverage_plan(requirements, planner)

    assert outcome.plan == proposed
    assert outcome.primary_attempts == 1
    assert not outcome.used_fallback
    assert len(calls) == 1


def test_retries_invalid_output_then_succeeds(requirements):
    proposed = build_deterministic_plan(requirements)
    planner, calls = fake_planner([{}, proposed])

    outcome = create_coverage_plan(requirements, planner)

    assert outcome.plan == proposed
    assert outcome.primary_attempts == 2
    assert not outcome.used_fallback
    assert len(calls) == 2


def test_exhausted_attempts_use_deterministic_fallback(requirements):
    planner, calls = fake_planner([{}, {}, {}])

    outcome = create_coverage_plan(requirements, planner)

    assert outcome.plan == build_deterministic_plan(requirements)
    assert outcome.primary_attempts == 3
    assert outcome.used_fallback
    assert len(calls) == 3


def test_invented_skill_is_not_accepted(requirements):
    proposed = build_deterministic_plan(requirements)
    proposed.prioritized_skills[0] = "java"
    proposed.slots[0].skill = "java"

    planner, calls = fake_planner([proposed, proposed, proposed])

    outcome = create_coverage_plan(requirements, planner)

    assert outcome.used_fallback
    assert outcome.plan.prioritized_skills == ["python", "sql"]
    assert len(calls) == 3


@pytest.mark.parametrize(
    ("error_type", "status_code"),
    [
        (AuthenticationError, 401),
        (RateLimitError, 429),
    ],
)
def test_provider_rejection_falls_back_without_retry(
    requirements,
    error_type,
    status_code,
):
    calls = []

    def reject_request(inputs):
        calls.append(inputs)
        response = httpx.Response(
            status_code,
            request=httpx.Request("POST", "https://api.groq.com"),
        )
        raise error_type(
            "Simulated provider rejection.",
            response=response,
            body=None,
        )

    planner = RunnableLambda(reject_request)

    outcome = create_coverage_plan(requirements, planner)

    assert outcome.used_fallback
    assert outcome.primary_attempts == 1
    assert outcome.plan == build_deterministic_plan(requirements)
    assert len(calls) == 1
