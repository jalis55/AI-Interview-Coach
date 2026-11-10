"""Tests for validating plans against confirmed requirements."""

import pytest

from ai_interview_coach.models.job import JobRequirements
from ai_interview_coach.models.plan import Difficulty, QuestionType
from ai_interview_coach.planning.allocation import build_deterministic_plan
from ai_interview_coach.planning.validation import (
    validate_plan_for_requirements,
)


@pytest.fixture
def requirements():
    return JobRequirements(
        role="Backend Engineer",
        seniority="mid",
        core_skills=["python", "sql"],
    )


def test_accepts_matching_plan_as_independent_snapshot(requirements):
    plan = build_deterministic_plan(requirements)

    validated = validate_plan_for_requirements(plan, requirements)

    assert validated == plan
    assert validated is not plan
    assert validated.slots is not plan.slots
    assert validated.prioritized_skills is not plan.prioritized_skills


def test_rejects_invented_skill(requirements):
    plan = build_deterministic_plan(requirements)
    plan.prioritized_skills[0] = "java"
    plan.slots[0].skill = "java"

    with pytest.raises(ValueError, match="account for all core skills"):
        validate_plan_for_requirements(plan, requirements)


def test_rejects_incorrect_question_count(requirements):
    plan = build_deterministic_plan(requirements)
    plan.slots.insert(0, plan.slots[0].model_copy())
    plan.num_questions = 4

    with pytest.raises(ValueError, match="required formula"):
        validate_plan_for_requirements(plan, requirements)


def test_rejects_omitting_a_skill_when_all_fit(requirements):
    plan = build_deterministic_plan(requirements)
    plan.prioritized_skills = ["python"]
    plan.omitted_skills = ["sql"]
    plan.slots[1].skill = "python"

    with pytest.raises(ValueError, match="prioritize up to nine"):
        validate_plan_for_requirements(plan, requirements)


def test_rejects_wrong_target_difficulty(requirements):
    plan = build_deterministic_plan(requirements)
    plan.slots[0].target_difficulty = Difficulty.HARD

    with pytest.raises(ValueError, match="seniority policy"):
        validate_plan_for_requirements(plan, requirements)


def test_revalidates_mutated_lists(requirements):
    plan = build_deterministic_plan(requirements)
    plan.prioritized_skills.append("python")

    with pytest.raises(ValueError, match="duplicates"):
        validate_plan_for_requirements(plan, requirements)


def test_accepts_different_priority_order(requirements):
    plan = build_deterministic_plan(requirements)
    plan.prioritized_skills.reverse()

    technical = [slot for slot in plan.slots if slot.question_type == QuestionType.TECHNICAL]
    technical[0].skill = "sql"
    technical[1].skill = "python"

    validated = validate_plan_for_requirements(plan, requirements)

    assert validated.prioritized_skills == ["sql", "python"]


def test_rejects_noncanonical_behavioral_label(requirements):
    plan = build_deterministic_plan(requirements)
    plan.slots[-1].skill = "communication"

    with pytest.raises(ValueError, match="behavioral skill label"):
        validate_plan_for_requirements(plan, requirements)
