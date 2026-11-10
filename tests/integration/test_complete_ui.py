"""User-visible interview, report, practice, and retry flows with fake providers."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from ai_interview_coach.models.session import InterviewStatus
from ai_interview_coach.ui import app as app_ui
from ai_interview_coach.ui import interview as interview_ui


def button(app, label):
    return next(b for b in app.button if b.label == label)


def answer(app, text="A clear explanation with an example."):
    next(a for a in app.text_area if a.label == "Your answer").input(text)
    button(app, "Submit answer").click().run()
    assert not app.exception


def test_browser_flow_through_report_practice_and_fresh_retry(interview_harness, monkeypatch):
    h = interview_harness
    monkeypatch.setattr(app_ui, "get_settings", lambda: h.settings)
    monkeypatch.setattr(interview_ui, "create_interview_service", lambda *args: h.service)
    session = h.create()
    app = AppTest.from_file(Path(__file__).resolve().parents[2] / "app.py")
    app.session_state["session_store"] = h.sessions
    app.session_state["history_store"] = h.histories
    app.session_state["lineage_store"] = h.lineages
    app.session_state["active_session_id"] = session.session_id
    app.run()
    assert not app.exception
    button(app, "Start interview").click().run()
    assert not app.exception
    turn = session.progress.current_turn_id
    question = session.progress.current_question.question
    app.run()
    assert session.progress.current_turn_id == turn
    assert session.progress.current_question.question == question
    assert h.calls == []
    answer(app, "   ")
    assert session.progress.current_index == 0
    assert h.calls == []
    for _ in range(3):
        answer(app)
    assert session.status is InterviewStatus.COMPLETED
    assert session.final_report
    assert any("JD preparation report" in s.value for s in app.subheader)
    app.run()
    assert len(h.calls) == 3
    next(m for m in app.multiselect if m.label == "Practice focus").set_value(["python"])
    button(app, "Start focused practice").click().run()
    assert not app.exception
    assert session.progress.round_kind == "practice"
    assert len(session.progress.round_slots) == 3
    for _ in range(3):
        answer(app)
    assert session.final_report.evaluated_count == 6
    button(app, "Fresh interview on same JD").click().run()
    assert not app.exception
    fresh = h.sessions.get(app.session_state["active_session_id"])
    assert fresh.session_id != session.session_id
    assert fresh.progress.records == []
    assert fresh.search_calls_by_skill == {}
    assert len(fresh.asked_questions) == 6
    assert all(b.label != "Start interview" for b in app.button)
    assert any(b.label == "Prepare questions" for b in app.button)


def test_new_jd_resets_lineage_and_pending_review(interview_harness, monkeypatch):
    h = interview_harness
    monkeypatch.setattr(app_ui, "get_settings", lambda: h.settings)
    session = h.create()
    app = AppTest.from_file(Path(__file__).resolve().parents[2] / "app.py")
    app.session_state["session_store"] = h.sessions
    app.session_state["active_session_id"] = session.session_id
    app.run()
    button(app, "New job description").click().run()
    assert not app.exception
    new = h.sessions.get(app.session_state["active_session_id"])
    assert new.requirements is None
    assert new.lineage_id != session.lineage_id
    assert any(a.label == "Job description" for a in app.text_area)
