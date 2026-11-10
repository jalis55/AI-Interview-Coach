"""Job-description input and parsing controls."""

from uuid import uuid4

import streamlit as st

from ai_interview_coach.chains.jd_parser import (
    build_jd_fallback_parser,
    build_jd_parser,
)
from ai_interview_coach.config import get_settings
from ai_interview_coach.models.session import InterviewSession
from ai_interview_coach.services.jd_parser import (
    JDParsingError,
    JDParsingService,
)


def render_jd_input(session: InterviewSession) -> None:
    with st.form("jd_input_form"):
        jd_text = st.text_area(
            "Job description",
            height=280,
            max_chars=30_000,
            placeholder="Paste the role, responsibilities, and required skills.",
        )
        submitted = st.form_submit_button("Analyze job description")

    if not submitted:
        return

    # A new submission invalidates any previous unconfirmed extraction.
    st.session_state.pop("pending_jd_result", None)

    if not jd_text.strip():
        st.warning("Please paste a job description.")
        return

    settings = get_settings()
    service = JDParsingService(
        primary=build_jd_parser(),
        fallback=build_jd_fallback_parser(),
        primary_max_attempts=settings.primary_max_attempts,
        fallback_max_attempts=settings.fallback_max_attempts,
        session=session,
    )

    try:
        with st.spinner("Analyzing your job description..."):
            outcome = service.parse(jd_text)
    except JDParsingError as error:
        st.error(str(error))
        return

    if outcome.exhausted:
        st.error(outcome.result.message)
        return

    if outcome.result.status == "needs_correction":
        st.warning(outcome.result.message)
        return

    session.jd_context = jd_text.strip()
    st.session_state["pending_jd_result"] = outcome.result

    st.session_state["jd_review_id"] = uuid4().hex
