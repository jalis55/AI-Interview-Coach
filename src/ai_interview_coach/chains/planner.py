"""LLM coverage planning with application-owned validation."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda

from ai_interview_coach.models.job import JobRequirements
from ai_interview_coach.models.plan import QuestionPlan
from ai_interview_coach.planning.allocation import (
    calculate_question_count,
    initial_target_difficulty,
)
from ai_interview_coach.planning.validation import (
    validate_plan_for_requirements,
)
from ai_interview_coach.prompts.prompt_planner import (
    PLANNER_HUMAN_PROMPT,
    PLANNER_SYSTEM_PROMPT,
)
from ai_interview_coach.providers.groq import create_chat_model


def build_planner(
    requirements: JobRequirements,
    jd_context: str,
) -> Runnable:
    confirmed = JobRequirements.model_validate(requirements.model_dump())

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PLANNER_SYSTEM_PROMPT),
            ("human", PLANNER_HUMAN_PROMPT),
        ]
    ).partial(
        requirements_json=confirmed.model_dump_json(),
        jd_context=jd_context,
        num_questions=calculate_question_count(len(confirmed.core_skills)),
        target_difficulty=initial_target_difficulty(confirmed.seniority).value,
    )

    structured_model = create_chat_model().with_structured_output(
        QuestionPlan,
        method="json_schema",
        strict=False,
    )

    def validate_output(plan: QuestionPlan) -> QuestionPlan:
        return validate_plan_for_requirements(plan, confirmed)

    return prompt | structured_model | RunnableLambda(validate_output)
