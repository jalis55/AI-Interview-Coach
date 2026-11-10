"""Research argument and authorization tests without provider calls."""

import pytest
from pydantic import ValidationError

from ai_interview_coach.models.job import JobRequirements
from ai_interview_coach.models.research import QuestionResearchRequest
from ai_interview_coach.planning.allocation import build_deterministic_plan
from ai_interview_coach.tools.research_policy import (
    ResearchAuthorizationError,
    authorize_research_request,
)


@pytest.fixture
def requirements():
    return JobRequirements(
        role="Backend Engineer",
        seniority="mid",
        core_skills=["python", "sql"],
        nice_to_have=["docker"],
    )


def test_request_normalizes_skill():
    request = QuestionResearchRequest(skill="  REST   API Development ")

    assert request.skill == "rest api development"


@pytest.mark.parametrize(
    "arguments",
    [
        {"skill": ""},
        {"skill": "   "},
        {"skill": "python", "max_results": 100},
        {"skill": "python", "search_budget": 10},
    ],
)
def test_request_rejects_invalid_arguments(arguments):
    with pytest.raises(ValidationError):
        QuestionResearchRequest.model_validate(arguments)


def test_selected_core_skill_is_authorized(requirements):
    plan = build_deterministic_plan(requirements)

    skill = authorize_research_request(
        QuestionResearchRequest(skill=" Python "),
        requirements=requirements,
        plan=plan,
    )

    assert skill == "python"


@pytest.mark.parametrize("skill", ["docker", "java", "behavioral"])
def test_unselected_skill_is_rejected(requirements, skill):
    plan = build_deterministic_plan(requirements)

    with pytest.raises(ResearchAuthorizationError):
        authorize_research_request(
            QuestionResearchRequest(skill=skill),
            requirements=requirements,
            plan=plan,
        )


def test_omitted_core_skill_is_rejected():
    requirements = JobRequirements(
        role="Software Engineer",
        seniority="mid",
        core_skills=[f"skill_{index}" for index in range(10)],
    )
    plan = build_deterministic_plan(requirements)

    assert plan.omitted_skills == ["skill_9"]

    with pytest.raises(ResearchAuthorizationError):
        authorize_research_request(
            QuestionResearchRequest(skill="skill_9"),
            requirements=requirements,
            plan=plan,
        )


def test_tampered_plan_is_rejected(requirements):
    plan = build_deterministic_plan(requirements)
    plan.prioritized_skills[0] = "java"
    plan.slots[0].skill = "java"

    with pytest.raises(ValueError, match="account for all core skills"):
        authorize_research_request(
            QuestionResearchRequest(skill="java"),
            requirements=requirements,
            plan=plan,
        )
