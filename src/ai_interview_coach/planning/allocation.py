from ai_interview_coach.models.job import JobRequirements, Seniority
from ai_interview_coach.models.plan import (
    Difficulty,
    QuestionPlan,
    QuestionSlot,
    QuestionType,
)


def initial_target_difficulty(seniority: Seniority) -> Difficulty:
    mapping = {
        Seniority.JUNIOR: Difficulty.EASY,
        Seniority.MID: Difficulty.MEDIUM,
        Seniority.SENIOR: Difficulty.HARD,
        Seniority.STAFF: Difficulty.HARD,
    }
    return mapping[seniority]


def build_deterministic_plan(
    requirements: JobRequirements,
) -> QuestionPlan:
    core_skills = requirements.core_skills
    num_questions = calculate_question_count(len(core_skills))
    difficulty = initial_target_difficulty(requirements.seniority)

    prioritized_skills = core_skills[:9]
    omitted_skills = core_skills[9:]

    technical_skills = list(prioritized_skills)

    if len(prioritized_skills) == 1:
        technical_skills.append(prioritized_skills[0])

    slots = [
        QuestionSlot(
            skill=skill,
            question_type=QuestionType.TECHNICAL,
            target_difficulty=difficulty,
        )
        for skill in technical_skills
    ]

    slots.append(
        QuestionSlot(
            skill="behavioral",
            question_type=QuestionType.BEHAVIORAL,
            target_difficulty=difficulty,
        )
    )

    return QuestionPlan(
        num_questions=num_questions,
        slots=slots,
        prioritized_skills=prioritized_skills,
        omitted_skills=omitted_skills,
    )


def calculate_question_count(core_skill_count: int) -> int:
    if type(core_skill_count) is not int:
        raise ValueError("Core skill count must be an integer.")

    if core_skill_count < 1:
        raise ValueError("At least one core skill is required.")

    return min(10, max(3, core_skill_count + 1))
