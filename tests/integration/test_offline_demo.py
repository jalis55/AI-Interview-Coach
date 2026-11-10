"""The shipped offline demo completes without invoking either provider."""

from pathlib import Path

import requests
from langchain_groq import ChatGroq
from streamlit.testing.v1 import AppTest

from ai_interview_coach.config import get_settings


def test_offline_demo_finishes_report_and_practice_without_network(monkeypatch):
    for name in ["GROQ_API_KEY", "TAVILY_API_KEY", "GROQ_MODEL"]:
        monkeypatch.setenv(name, "offline-demo")
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()

    def forbidden(*args, **kwargs):
        raise AssertionError("Offline demo must not invoke a provider")

    monkeypatch.setattr(ChatGroq, "_generate", forbidden)
    monkeypatch.setattr(requests.Session, "post", forbidden)
    try:
        app = AppTest.from_file(Path(__file__).resolve().parents[2] / "demo.py", default_timeout=15)
        app.run()
        assert not app.exception
        next(b for b in app.button if b.label == "Start interview").click().run()
        assert not app.exception
        for _ in range(3):
            next(a for a in app.text_area if a.label == "Your answer").input("Demo answer")
            next(b for b in app.button if b.label == "Submit answer").click().run()
            assert not app.exception
        session = app.session_state["session_store"].get(app.session_state["active_session_id"])
        assert session.is_demo
        assert session.final_report.readiness_status == "unavailable"
        assert session.final_report.defaulted_count == 3
        assert session.usage.provider_calls == 0
        assert session.search_calls_by_skill == {}
        next(m for m in app.multiselect if m.label == "Practice focus").set_value(["python"])
        next(b for b in app.button if b.label == "Start focused practice").click().run()
        assert not app.exception
        assert session.progress.round_kind == "practice"
        assert session.usage.provider_calls == 0
    finally:
        get_settings.cache_clear()
