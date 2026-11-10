"""Coverage UI checks without provider requests."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.runnables import RunnableLambda
from streamlit.testing.v1 import AppTest

from ai_interview_coach.models.job import JobRequirements
from ai_interview_coach.models.session import InterviewStatus
from ai_interview_coach.planning.allocation import build_deterministic_plan
from ai_interview_coach.stores.session_store import InMemorySessionStore
from ai_interview_coach.ui import app as app_ui
from ai_interview_coach.ui import planning as planning_ui


@pytest.mark.parametrize("use_fallback", [False, True])
def test_plan_creation_rerun_and_edit(monkeypatch, use_fallback):
    settings = SimpleNamespace(primary_max_attempts=3)
    monkeypatch.setattr(app_ui, "get_settings", lambda: settings)
    monkeypatch.setattr(planning_ui, "get_settings", lambda: settings)

    store = InMemorySessionStore()
    session = store.create()
    session.requirements = JobRequirements(
        role="Backend Engineer", seniority="mid", core_skills=["python", "sql"]
    )
    session.jd_context = "Backend role emphasizing Python and SQL."
    calls = []

    def build(requirements, context):
        assert context == session.jd_context

        def invoke(inputs):
            calls.append(inputs)
            return {} if use_fallback else build_deterministic_plan(requirements)

        return RunnableLambda(invoke)

    monkeypatch.setattr(planning_ui, "build_planner", build)
    app = AppTest.from_file(Path(__file__).resolve().parents[2] / "app.py")
    app.session_state["session_store"] = store
    app.session_state["active_session_id"] = session.session_id
    app.run()
    assert not app.exception
    assert calls == []

    next(b for b in app.button if b.label == "Create interview plan").click().run()
    assert not app.exception
    assert session.status is InterviewStatus.READY
    assert session.plan.num_questions == 3
    assert session.plan_used_fallback is use_fallback
    assert session.planning_attempts == (3 if use_fallback else 1)
    assert any(s.value == "Status: ready" for s in app.sidebar.markdown)
    assert len(app.table) == 1

    previous_calls = len(calls)
    app.run()
    assert len(calls) == previous_calls

    next(b for b in app.button if b.label == "Edit requirements").click().run()
    assert not app.exception
    assert session.status is InterviewStatus.DRAFT
    assert session.plan is None
    assert session.requirements is None
    assert session.jd_context == "Backend role emphasizing Python and SQL."
    assert app.session_state["pending_jd_result"].requirements.core_skills == ["python", "sql"]
    assert len(calls) == previous_calls


def test_unconfirmed_session_has_no_planning_button(monkeypatch):
    monkeypatch.setattr(app_ui, "get_settings", lambda: SimpleNamespace())
    app = AppTest.from_file(Path(__file__).resolve().parents[2] / "app.py").run()
    assert not app.exception
    assert all(b.label != "Create interview plan" for b in app.button)
