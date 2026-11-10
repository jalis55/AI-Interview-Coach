"""Validate proposed plans against confirmed job requirements."""

from collections import Counter

from ai_interview_coach.models.job import JobRequirements
from ai_interview_coach.models.plan import QuestionPlan, QuestionType
from ai_interview_coach.planning.allocation import (
    calculate_question_count,
    initial_target_difficulty,
)


def validate_plan_for_requirements(
    plan: QuestionPlan,
    requirements: JobRequirements,
) -> QuestionPlan:
    # Revalidate a snapshot, including any lists changed after creation.
    validated = QuestionPlan.model_validate(plan.model_dump())

    if any(
        slot.question_type == QuestionType.BEHAVIORAL and slot.skill != "behavioral"
        for slot in validated.slots
    ):
        raise ValueError("The behavioral slot must use the behavioral skill label.")

    core_skills = set(requirements.core_skills)
    prioritized = set(validated.prioritized_skills)
    omitted = set(validated.omitted_skills)

    expected_count = calculate_question_count(len(core_skills))

    if validated.num_questions != expected_count:
        raise ValueError("Question count does not match the required formula.")

    if prioritized | omitted != core_skills:
        raise ValueError(
            "Prioritized and omitted skills must account for all core skills "
            "without adding other skills."
        )

    if len(prioritized) != min(9, len(core_skills)):
        raise ValueError("The plan must prioritize up to nine core skills.")

    technical_counts = Counter(
        slot.skill for slot in validated.slots if slot.question_type == QuestionType.TECHNICAL
    )

    expected_per_skill = 2 if len(core_skills) == 1 else 1

    if any(technical_counts[skill] != expected_per_skill for skill in prioritized):
        raise ValueError("Technical slots are not allocated correctly.")

    expected_difficulty = initial_target_difficulty(requirements.seniority)

    if any(slot.target_difficulty != expected_difficulty for slot in validated.slots):
        raise ValueError("Target difficulty must match the seniority policy.")

    return validated
