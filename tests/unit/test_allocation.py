"""Tests for deterministic coverage allocation."""

import pytest

from ai_interview_coach.models.job import JobRequirements, Seniority
from ai_interview_coach.models.plan import Difficulty, QuestionType
from ai_interview_coach.planning.allocation import (
    build_deterministic_plan,
    calculate_question_count,
    initial_target_difficulty,
)


@pytest.mark.parametrize(
    ("skill_count", "expected"),
    [
        (1, 3),
        (2, 3),
        (3, 4),
        (9, 10),
        (10, 10),
        (20, 10),
    ],
)
def test_question_count_formula(skill_count, expected):
    assert calculate_question_count(skill_count) == expected


@pytest.mark.parametrize("skill_count", [0, -1, True, 2.0, "2"])
def test_question_count_rejects_invalid_input(skill_count):
    with pytest.raises(ValueError):
        calculate_question_count(skill_count)


@pytest.mark.parametrize("skill_count", [1, 2, 9, 10, 15])
def test_deterministic_plan_allocates_expected_slots(skill_count):
    skills = [f"skill_{index}" for index in range(skill_count)]
    requirements = JobRequirements(
        role="Software Engineer",
        seniority="mid",
        core_skills=skills,
    )

    plan = build_deterministic_plan(requirements)

    technical = [slot for slot in plan.slots if slot.question_type == QuestionType.TECHNICAL]
    behavioral = [slot for slot in plan.slots if slot.question_type == QuestionType.BEHAVIORAL]

    expected_counts = {
        1: 3,
        2: 3,
        9: 10,
        10: 10,
        15: 10,
    }

    assert plan.num_questions == expected_counts[skill_count]
    assert len(plan.slots) == expected_counts[skill_count]
    assert len(behavioral) == 1
    assert behavioral[0].skill == "behavioral"
    assert plan.prioritized_skills == skills[:9]
    assert plan.omitted_skills == skills[9:]

    expected_technical_skills = skills[:9]
    if skill_count == 1:
        expected_technical_skills = [skills[0], skills[0]]

    assert [slot.skill for slot in technical] == expected_technical_skills
    assert all(slot.target_difficulty is Difficulty.MEDIUM for slot in plan.slots)


@pytest.mark.parametrize(
    ("seniority", "expected"),
    [
        (Seniority.JUNIOR, Difficulty.EASY),
        (Seniority.MID, Difficulty.MEDIUM),
        (Seniority.SENIOR, Difficulty.HARD),
        (Seniority.STAFF, Difficulty.HARD),
    ],
)
def test_initial_difficulty_mapping(seniority, expected):
    assert initial_target_difficulty(seniority) is expected


def test_nice_to_have_skills_are_not_planned():
    requirements = JobRequirements(
        role="Backend Engineer",
        seniority="mid",
        core_skills=["python", "sql"],
        nice_to_have=["docker"],
    )

    plan = build_deterministic_plan(requirements)

    assert plan.prioritized_skills == ["python", "sql"]
    assert plan.omitted_skills == []
    assert "docker" not in [slot.skill for slot in plan.slots]


def test_planning_preserves_confirmed_requirements():
    requirements = JobRequirements(
        role="Backend Engineer",
        seniority="mid",
        core_skills=["python", "sql"],
    )
    original = requirements.model_dump()

    plan = build_deterministic_plan(requirements)
    plan.prioritized_skills.append("extra")

    assert requirements.model_dump() == original
