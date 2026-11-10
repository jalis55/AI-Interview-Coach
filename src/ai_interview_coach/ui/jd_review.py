"""Review and confirm extracted job requirements."""

import streamlit as st
from pydantic import ValidationError

from ai_interview_coach.models.job import JobRequirements, Seniority
from ai_interview_coach.models.session import InterviewSession


def render_jd_review(session: InterviewSession) -> None:
    pending = st.session_state.get("pending_jd_result")

    if pending is None or pending.requirements is None:
        return

    requirements = pending.requirements
    review_id = st.session_state["jd_review_id"]
    seniorities = [level.value for level in Seniority]

    st.subheader("Review job requirements")
    st.info(pending.message)

    with st.form(f"jd_review_{review_id}"):
        role = st.text_input(
            "Role",
            value=requirements.role,
        )
        seniority = st.selectbox(
            "Seniority",
            options=seniorities,
            index=seniorities.index(requirements.seniority.value),
        )
        core_skills = st.text_area(
            "Core skills — one per line",
            value="\n".join(requirements.core_skills),
        )
        nice_to_have = st.text_area(
            "Nice-to-have skills — one per line",
            value="\n".join(requirements.nice_to_have),
        )
        confirmed = st.form_submit_button("Confirm requirements")

    if not confirmed:
        return

    try:
        corrected = JobRequirements(
            role=role,
            seniority=seniority,
            core_skills=[line.strip() for line in core_skills.splitlines() if line.strip()],
            nice_to_have=[line.strip() for line in nice_to_have.splitlines() if line.strip()],
        )
    except ValidationError:
        st.warning("Provide a role and at least one core skill.")
        return

    session.requirements = corrected
    st.session_state.pop("pending_jd_result", None)
    st.session_state.pop("jd_review_id", None)
    st.rerun()
