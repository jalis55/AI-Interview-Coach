"""Streamlit application shell."""

from uuid import uuid4

import streamlit as st
from pydantic import ValidationError

from ai_interview_coach.config import get_settings
from ai_interview_coach.models.interview import InterviewProgress
from ai_interview_coach.models.jd_parse import JDParseResult
from ai_interview_coach.models.session import InterviewStatus
from ai_interview_coach.services.demo import load_demo
from ai_interview_coach.stores.history_store import InMemoryHistoryStore
from ai_interview_coach.stores.lineage_store import InMemoryLineageStore
from ai_interview_coach.stores.session_store import InMemorySessionStore
from ai_interview_coach.ui.interview import render_interview
from ai_interview_coach.ui.jd_input import render_jd_input
from ai_interview_coach.ui.jd_review import render_jd_review
from ai_interview_coach.ui.planning import render_planning
from ai_interview_coach.ui.research import render_research, render_research_activity


def initialize_state() -> None:
    if "session_store" not in st.session_state:
        st.session_state["session_store"] = InMemorySessionStore()

    if "history_store" not in st.session_state:
        st.session_state["history_store"] = InMemoryHistoryStore()

    if "lineage_store" not in st.session_state:
        st.session_state["lineage_store"] = InMemoryLineageStore()

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
        settings = get_settings()
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
    if getattr(settings, "demo_mode", False) and session.requirements is None:
        load_demo(session)

    st.title("AI Interview Coach")
    st.write("Prepare for the skills and responsibilities in your job description.")

    with st.sidebar:
        st.subheader("Current interview")
        st.caption(f"Session ID: {session.session_id}")
        st.write(f"Status: {session.status.value}")
        if st.button("New job description"):
            fresh = store.create()
            st.session_state["active_session_id"] = fresh.session_id
            st.session_state.pop("pending_jd_result", None)
            st.session_state.pop("jd_review_id", None)
            st.rerun()
        if st.button("Load offline demo"):
            fresh = load_demo(store.create())
            st.session_state["active_session_id"] = fresh.session_id
            st.session_state.pop("pending_jd_result", None)
            st.session_state.pop("jd_review_id", None)
            st.rerun()
        with st.expander("Usage", expanded=False):
            usage = session.usage
            st.write(f"LLM requests attempted: {usage.provider_calls}")
            st.write(f"LLM requests failed: {usage.failed_calls}")
            st.write(f"Input tokens reported: {usage.input_tokens}")
            st.write(f"Output tokens reported: {usage.output_tokens}")
            st.write(f"Responses reporting usage: {usage.metered_responses}")
            st.write(f"Retry attempts: {usage.retry_attempts}")
            st.write(f"Fallback paths entered: {usage.fallback_runs}")
            st.write(f"Safe defaults used: {usage.safe_defaults}")
            st.write(f"Search allowances consumed: {sum(session.search_calls_by_skill.values())}")
            st.write("Calls by stage", usage.calls_by_stage)
            st.caption(
                "Tokens count only provider-reported usage. Failed calls may be unmetered. "
                "No estimated price is quoted."
            )

    render_research_activity(session)

    if session.requirements is None:
        render_jd_input(session)
        render_jd_review(session)
    else:
        st.success("Job requirements confirmed.")
        with st.expander("Confirmed requirements", expanded=not session.progress.round_slots):
            st.json(session.requirements.model_dump(mode="json"))

        if not session.progress.round_slots and st.button("Edit requirements"):
            st.session_state["pending_jd_result"] = JDParseResult(
                status="valid",
                requirements=session.requirements.model_copy(deep=True),
                message="Review your changes and confirm the requirements again.",
            )
            st.session_state["jd_review_id"] = uuid4().hex

            session.requirements = None
            session.plan = None
            session.plan_used_fallback = False
            session.planning_attempts = 0
            session.candidate_pool = []
            session.research_complete = False
            session.progress = InterviewProgress()
            session.pending_evaluations = {}
            session.final_report = None
            session.status = InterviewStatus.DRAFT
            st.rerun()

        with st.expander("Coverage and research", expanded=not session.progress.round_slots):
            render_planning(session)
            render_research(session)
        render_interview(
            session,
            settings=settings,
            sessions=store,
            histories=st.session_state["history_store"],
            lineages=st.session_state["lineage_store"],
        )
