"""End-to-end research orchestration with injected providers."""

import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableLambda

from ai_interview_coach.config import Settings
from ai_interview_coach.models.job import JobRequirements
from ai_interview_coach.models.question import InterviewQuestion, QuestionBatch
from ai_interview_coach.models.research import SearchOutcome
from ai_interview_coach.models.session import InterviewSession, InterviewStatus
from ai_interview_coach.planning.allocation import build_deterministic_plan
from ai_interview_coach.services.research import ResearchPreparationError, ResearchService

Q1 = "How do Python generators manage lazy iteration?"
Q2 = "What trade-offs matter when testing Python exception handling?"
URL = "https://example.com/python"


def question(text=Q1, **changes):
    return InterviewQuestion(
        **(
            dict(
                question=text,
                skill="python",
                difficulty="medium",
                source="web",
                source_url=URL,
                rationale="Assesses practical Python knowledge.",
            )
            | changes
        )
    )


def make_session(skills=None):
    requirements = JobRequirements(
        role="Engineer", seniority="mid", core_skills=skills or ["python"]
    )
    return InterviewSession(
        requirements=requirements,
        plan=build_deterministic_plan(requirements),
        status=InterviewStatus.READY,
    )


def make_service(
    *,
    search=None,
    planner=None,
    extractor=None,
    extractor_fallback=None,
    generator=None,
    generator_fallback=None,
):
    settings = Settings(
        _env_file=None,
        groq_api_key="fake-groq",
        tavily_api_key="fake-tavily",
        groq_model="test-model",
        tool_loop_max_iterations=2,
    )
    empty = RunnableLambda(lambda _: QuestionBatch(questions=[]))
    return ResearchService(
        settings=settings,
        search=search or (lambda *_: SearchOutcome(status="empty")),
        tool_planner=planner or RunnableLambda(lambda _: AIMessage(content="Done")),
        extractor=extractor or empty,
        extractor_fallback=extractor_fallback or empty,
        generator=generator or empty,
        generator_fallback=generator_fallback or empty,
    )


def web_search(*args):
    return SearchOutcome(
        status="success",
        snippets=[
            {
                "title": "Evidence",
                "url": URL,
                "content": Q1 + " " + Q2,
            }
        ],
    )


def tool_call(skill="python", name="find_interview_questions", args=None, id="call_1"):
    return AIMessage(
        content="",
        tool_calls=[
            {
                "id": id,
                "name": name,
                "args": args if args is not None else {"skill": skill},
            }
        ],
    )


def test_valid_tool_call_builds_web_pool_and_repeated_prepare_makes_no_calls():
    calls = []
    planner_calls = []

    def search(*args):
        calls.append(args)
        return web_search()

    def plan(messages):
        planner_calls.append(messages)
        return tool_call()

    service = make_service(
        search=search,
        planner=RunnableLambda(plan),
        extractor=RunnableLambda(lambda _: QuestionBatch(questions=[question(), question(Q2)])),
    )
    session = make_session()
    service.prepare(session)
    assert session.research_complete
    assert session.status is InterviewStatus.PREPARING
    python = [q for q in session.candidate_pool if q.skill == "python"]
    assert len(python) == 2
    assert all(q.source == "web" and q.source_title == "Evidence" for q in python)
    assert any(q.skill == "behavioral" for q in session.candidate_pool)
    service.prepare(session)
    assert len(calls) == len(planner_calls) == 1
    assert session.search_calls_by_skill == {"python": 1}


def test_extraction_repairs_use_identical_cached_snippets_without_search_retry():
    search_calls, primary_values, fallback_values = [], [], []

    def search(*args):
        search_calls.append(args)
        return web_search()

    def broken(values):
        primary_values.append(values.copy())
        return {}

    def repaired(values):
        fallback_values.append(values.copy())
        return QuestionBatch(questions=[question(), question(Q2)])

    service = make_service(
        search=search,
        extractor=RunnableLambda(broken),
        extractor_fallback=RunnableLambda(repaired),
    )
    session = make_session()
    service.find_interview_questions(session, "python")
    assert len(search_calls) == 1
    assert len(primary_values) == 3
    assert len(fallback_values) == 1
    assert all(v["snippets"] == fallback_values[0]["snippets"] for v in primary_values)
    assert any(e.event_type == "fallback_started" for e in session.activity_log)


def test_extraction_exhaustion_still_generates_honestly_labeled_questions():
    seen = []

    def generate(values):
        seen.append(values)
        # A generated question cannot retain a web label, even with a real URL.
        return QuestionBatch(questions=[question(), question(Q2)])

    broken = RunnableLambda(lambda _: {})
    service = make_service(
        search=web_search,
        extractor=broken,
        extractor_fallback=broken,
        generator=RunnableLambda(generate),
    )
    session = make_session()
    service.find_interview_questions(session, "python")
    assert len(seen) == 1
    assert all(q.source == "llm_fallback" and q.source_url is None for q in session.candidate_pool)
    assert session.search_calls_by_skill == {"python": 1}


@pytest.mark.parametrize("status", ["empty", "error"])
def test_sparse_search_and_invalid_generation_have_bounded_safe_defaults(status):
    generation_calls, search_calls = [], []

    def malformed(values):
        generation_calls.append(values)
        return {}

    def search(*args):
        search_calls.append(args)
        return SearchOutcome(status=status)

    service = make_service(
        search=search,
        generator=RunnableLambda(malformed),
        generator_fallback=RunnableLambda(malformed),
    )
    session = make_session()
    batch = service.find_interview_questions(session, "python")
    assert len(generation_calls) == 5
    assert len(search_calls) == 1
    assert len(batch.questions) == 2
    assert all(q.source == "llm_fallback" for q in batch.questions)
    assert all("Generic skill practice" in q.rationale for q in batch.questions)
    service.find_interview_questions(session, "python")
    assert len(search_calls) == 1
    assert len(generation_calls) == 5


@pytest.mark.parametrize(
    "reply",
    [
        tool_call(name="delete_files"),
        tool_call(skill="java"),
        tool_call(args={"skill": "python", "max_results": 100}),
    ],
)
def test_invalid_tool_requests_are_not_executed(reply):
    calls, planner_calls = [], []

    def plan(messages):
        planner_calls.append(messages)
        return reply

    def search(skill, seniority):
        calls.append(skill)
        return SearchOutcome(status="empty")

    session = make_session()
    make_service(search=search, planner=RunnableLambda(plan)).prepare(session)
    assert calls == ["python"]  # Authorized deterministic fallback only.
    assert len(planner_calls) == 3
    assert any(e.event_type == "tool_plan_fallback" for e in session.activity_log)


def test_tool_loop_preserves_call_ids_and_stops_at_iteration_limit():
    planner_inputs, search_calls = [], []

    def plan(messages):
        planner_inputs.append(list(messages))
        return tool_call(id=f"call_{len(planner_inputs)}")

    def search(skill, seniority):
        search_calls.append(skill)
        return SearchOutcome(status="empty")

    session = make_session(["python", "sql"])
    make_service(search=search, planner=RunnableLambda(plan)).prepare(session)
    assert len(planner_inputs) == 2
    assert any(isinstance(m, ToolMessage) and m.tool_call_id == "call_1" for m in planner_inputs[1])
    assert search_calls == ["python", "sql"]
    assert session.research_complete


def test_asked_questions_are_excluded_and_source_queries_do_not_receive_jd():
    session = make_session()
    session.asked_questions = [Q1]
    session.jd_context = "PRIVATE JD CONTEXT"
    service = make_service(
        search=web_search,
        extractor=RunnableLambda(lambda _: QuestionBatch(questions=[question(), question(Q2)])),
    )
    service.prepare(session)
    assert all(q.question != Q1 for q in session.candidate_pool)
    serialized = json.dumps([e.model_dump(mode="json") for e in session.activity_log])
    assert "PRIVATE JD CONTEXT" not in serialized
    assert Q1 not in serialized
    assert "fake-groq" not in serialized


def test_novelty_failure_preserves_search_budget_for_recovery():
    service = make_service()
    session = make_session()
    from ai_interview_coach.tools.generic_questions import generic_question_texts

    session.asked_questions = generic_question_texts("python")
    with pytest.raises(ResearchPreparationError, match="unused questions"):
        service.prepare(session)
    assert session.status is InterviewStatus.RECOVERABLE_ERROR
    assert not session.research_complete
    assert session.search_calls_by_skill == {"python": 1}
    with pytest.raises(ResearchPreparationError):
        service.prepare(session)
    assert session.search_calls_by_skill == {"python": 1}


def test_candidate_pool_limit_is_enforced():
    service = make_service()
    service.settings.candidate_pool_limit = 1
    with pytest.raises(ResearchPreparationError, match="pool limit"):
        service.prepare(make_session())


def test_provider_outage_still_covers_a_full_nine_skill_plan():
    session = make_session([f"skill_{i}" for i in range(9)])
    service = make_service()
    service.prepare(session)
    assert session.research_complete
    assert len(session.candidate_pool) >= 10
    assert set(q.skill for q in session.candidate_pool) == {
        *session.plan.prioritized_skills,
        "behavioral",
    }
    assert all(count == 1 for count in session.search_calls_by_skill.values())


@pytest.mark.parametrize("code", ["json_validate_failed", "DO_NOT_LOG_SECRET"])
def test_provider_activity_contains_safe_status_and_allowlisted_code_only(code):
    import httpx
    from groq import BadRequestError

    response = httpx.Response(400, request=httpx.Request("POST", "https://api.groq.com"))

    def reject(values):
        raise BadRequestError(
            "DO_NOT_LOG_SECRET",
            response=response,
            body={"code": code, "message": "DO_NOT_LOG_SECRET"},
        )

    session = make_session()
    service = make_service(generator=RunnableLambda(reject))
    service.find_interview_questions(session, "python")
    event = next(e for e in session.activity_log if e.event_type == "provider_unavailable")
    assert event.metadata["provider"] == "groq"
    assert event.metadata["http_status"] == 400
    if code == "json_validate_failed":
        assert event.metadata["error_code"] == code
    else:
        assert "error_code" not in event.metadata
    assert "DO_NOT_LOG_SECRET" not in event.model_dump_json()


def test_just_in_time_generation_never_searches_and_preserves_target():
    from ai_interview_coach.models.plan import Difficulty

    def forbidden(*args):
        pytest.fail("Adaptive selection must not invoke search")

    service = make_service(search=forbidden)
    session = make_session()
    session.search_calls_by_skill = {"python": 1}
    question = service.generate_for_turn(session, "python", Difficulty.EASY)[0]
    assert question.difficulty is Difficulty.EASY
    assert question.source == "llm_fallback"
    assert session.plan.slots[0].target_difficulty is Difficulty.MEDIUM
    assert session.search_calls_by_skill == {"python": 1}
