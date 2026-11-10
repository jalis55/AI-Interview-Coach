"""Research preparation controls and safe activity display."""

from collections import Counter

import streamlit as st
from groq import APIError

from ai_interview_coach.config import get_settings
from ai_interview_coach.models.session import InterviewSession
from ai_interview_coach.services.research import (
    ResearchPreparationError,
    create_research_service,
)


def render_research(session: InterviewSession) -> None:
    if session.plan is None or session.requirements is None:
        return
    st.subheader("Prepare interview questions")
    if not session.research_complete:
        st.write("Research the selected skills and prepare questions for your interview.")
        if st.button("Prepare questions", type="primary"):
            try:
                with st.status("Preparing interview questions...", expanded=True) as status:
                    service = create_research_service(get_settings())
                    service.prepare(
                        session, on_skill_ready=lambda skill: st.text(f"Prepared: {skill}")
                    )
                    status.update(label="Question preparation complete", state="complete")
            except (ResearchPreparationError, APIError, ValueError):
                st.error(
                    "Question preparation could not finish. Your progress is preserved. "
                    "Try again to reuse existing research without repeating searches."
                )
                return
            st.rerun()
        return

    st.success("Question preparation complete.")
    rows = []
    for skill in [*session.plan.prioritized_skills, "behavioral"]:
        counts = Counter(q.source.value for q in session.candidate_pool if q.skill == skill)
        rows.append(
            {
                "Skill": skill,
                "From web sources": counts["web"],
                "Generated practice": counts["llm_fallback"],
            }
        )
    st.table(rows)
    if any(event.event_type == "safe_default" for event in session.activity_log):
        st.info("Generic skill questions were added where research or generation was limited.")
    st.caption(
        "Source labels describe where questions came from, not their quality. "
        "Web results are not verified questions from the target employer."
    )
    st.caption("The one-question-at-a-time interview is the next milestone.")


def render_research_activity(session: InterviewSession) -> None:
    with st.sidebar.expander("Research activity", expanded=False):
        if not session.activity_log:
            st.caption("No research activity yet.")
        for event in session.activity_log[-30:]:
            metadata = " | ".join(f"{key}: {value}" for key, value in event.metadata.items())
            st.text(f"{event.timestamp:%H:%M:%S} UTC | {event.event_type} | {event.status}")
            if metadata:
                st.caption(metadata)
