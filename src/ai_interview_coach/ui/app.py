"""Streamlit application shell."""

from uuid import uuid4

import streamlit as st
from pydantic import ValidationError

from ai_interview_coach.config import get_settings
from ai_interview_coach.models.jd_parse import JDParseResult
from ai_interview_coach.stores.history_store import InMemoryHistoryStore
from ai_interview_coach.stores.session_store import InMemorySessionStore
from ai_interview_coach.ui.jd_input import render_jd_input
from ai_interview_coach.ui.jd_review import render_jd_review


def initialize_state() -> None:
    if "session_store" not in st.session_state:
        st.session_state["session_store"] = InMemorySessionStore()

    if "history_store" not in st.session_state:
        st.session_state["history_store"] = InMemoryHistoryStore()

    if "active_session_id" not in st.session_state:
        store = st.session_state["session_store"]
        session = store.create()
        st.session_state["active_session_id"] = session.session_id


def main() -> None:
    st.set_page_config(
        page_title="AI Interview Coach",
        page_icon="🎯",
    )

    try:
        get_settings()
    except ValidationError:
        st.error(
            "Configuration is missing or invalid. "
            "Check GROQ_API_KEY, TAVILY_API_KEY, and GROQ_MODEL in your .env file. "
            "Also check any custom timeout or attempt limits."
        )
        st.stop()

    initialize_state()

    store = st.session_state["session_store"]
    session = store.get(st.session_state["active_session_id"])

    st.title("AI Interview Coach")
    st.write("Prepare for the skills and responsibilities in your job description.")

    with st.sidebar:
        st.subheader("Current interview")
        st.caption(f"Session ID: {session.session_id}")
        st.write(f"Status: {session.status.value}")

    if session.requirements is None:
        render_jd_input()
        render_jd_review(session)
    else:
        st.success("Job requirements confirmed.")
        st.json(session.requirements.model_dump(mode="json"))

        if st.button("Edit requirements"):
            st.session_state["pending_jd_result"] = JDParseResult(
                status="valid",
                requirements=session.requirements.model_copy(deep=True),
                message="Review your changes and confirm the requirements again.",
            )
            st.caption("Requirements confirmed. Question planning is the next step.")
            st.session_state["jd_review_id"] = uuid4().hex

            session.requirements = None
            st.rerun()
