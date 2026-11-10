"""Research button lifecycle with the real service and fake provider boundaries."""

from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from streamlit.testing.v1 import AppTest

from ai_interview_coach.config import Settings
from ai_interview_coach.models.job import JobRequirements
from ai_interview_coach.models.question import QuestionBatch
from ai_interview_coach.models.research import SearchOutcome
from ai_interview_coach.models.session import InterviewStatus
from ai_interview_coach.planning.allocation import build_deterministic_plan
from ai_interview_coach.services.research import ResearchService
from ai_interview_coach.stores.session_store import InMemorySessionStore
from ai_interview_coach.ui import app as app_ui
from ai_interview_coach.ui import research as research_ui


def test_prepare_button_persists_results_and_edit_preserves_spent_budget(monkeypatch):
    monkeypatch.setattr(app_ui, "get_settings", lambda: SimpleNamespace())
    settings = Settings(
        _env_file=None, groq_api_key="fake", tavily_api_key="fake", groq_model="test"
    )
    monkeypatch.setattr(research_ui, "get_settings", lambda: settings)
    calls = []

    def search(skill, seniority):
        calls.append(skill)
        return SearchOutcome(status="empty")

    empty = RunnableLambda(lambda _: QuestionBatch(questions=[]))
    service = ResearchService(
        settings=settings,
        search=search,
        tool_planner=RunnableLambda(lambda _: AIMessage(content="Done")),
        extractor=empty,
        extractor_fallback=empty,
        generator=empty,
        generator_fallback=empty,
    )
    monkeypatch.setattr(research_ui, "create_research_service", lambda _: service)
    store = InMemorySessionStore()
    session = store.create()
    session.requirements = JobRequirements(role="Engineer", seniority="mid", core_skills=["python"])
    session.plan = build_deterministic_plan(session.requirements)
    session.status = InterviewStatus.READY
    app = AppTest.from_file(Path(__file__).resolve().parents[2] / "app.py")
    app.session_state["session_store"] = store
    app.session_state["active_session_id"] = session.session_id
    app.run()
    assert calls == []
    next(b for b in app.button if b.label == "Prepare questions").click().run()
    assert not app.exception
    assert session.research_complete
    assert calls == ["python"]
    assert len(session.candidate_pool) == 3
    assert any(s.value == "Question preparation complete." for s in app.success)
    assert any("Generic skill questions" in i.value for i in app.info)
    assert all(b.label != "Prepare questions" for b in app.button)
    app.run()
    assert calls == ["python"]
    next(b for b in app.button if b.label == "Edit requirements").click().run()
    assert not app.exception
    assert not session.research_complete
    assert session.candidate_pool == []
    assert session.search_calls_by_skill == {"python": 1}
    assert session.search_cache
