"""Streamlit application shell."""

import streamlit as st
from pydantic import ValidationError

from ai_interview_coach.config import get_settings
from ai_interview_coach.stores.history_store import InMemoryHistoryStore
from ai_interview_coach.stores.session_store import InMemorySessionStore


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

    st.info("Job description input will be added in Milestone 2.")

    if st.button("Check rerun"):
        st.success("The script reran. Your session ID should stay the same.")
