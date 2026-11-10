"""Coverage planning controls and preview."""

import streamlit as st

from ai_interview_coach.chains.planner import build_planner
from ai_interview_coach.config import get_settings
from ai_interview_coach.models.session import InterviewSession, InterviewStatus
from ai_interview_coach.services.planning import create_coverage_plan


def render_planning(session: InterviewSession) -> None:
    if session.requirements is None:
        return

    st.subheader("Interview coverage")

    if session.plan is None:
        st.caption("Create a question plan from your confirmed requirements.")
        if st.button("Create interview plan", type="primary"):
            with st.spinner("Planning interview coverage..."):
                planner = build_planner(session.requirements, session.jd_context)
                outcome = create_coverage_plan(
                    session.requirements,
                    planner,
                    max_attempts=get_settings().primary_max_attempts,
                    session=session,
                )

            session.plan = outcome.plan
            session.plan_used_fallback = outcome.used_fallback
            session.planning_attempts = outcome.primary_attempts
            session.status = InterviewStatus.READY
            st.rerun()
        return

    plan = session.plan
    st.success(f"Interview plan ready: {plan.num_questions} questions.")

    if session.plan_used_fallback:
        st.warning(
            "Model planning was unavailable or did not produce an acceptable plan. "
            "Coverage uses confirmed skill-list order."
        )

    st.table(
        [
            {
                "Question": index,
                "Skill": slot.skill,
                "Type": slot.question_type.value,
                "Target difficulty": slot.target_difficulty.value,
            }
            for index, slot in enumerate(plan.slots, start=1)
        ]
    )
    st.write("Prioritized skills: " + ", ".join(plan.prioritized_skills))
    if plan.omitted_skills:
        st.warning("Not covered in this round: " + ", ".join(plan.omitted_skills))

    st.caption(
        "This round prioritizes breadth. One answer per skill cannot establish mastery. "
        "Difficulty adaptation becomes visible when a skill appears again, including "
        "during focused practice."
    )
    st.caption("Prepare questions below, then start the interview when you are ready.")
