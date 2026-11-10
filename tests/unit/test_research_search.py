"""One-shot research budgets and cache isolation."""

import pytest
from pydantic import ValidationError

from ai_interview_coach.models.job import JobRequirements
from ai_interview_coach.models.research import QuestionResearchRequest, SearchOutcome, SearchStatus
from ai_interview_coach.models.session import InterviewSession
from ai_interview_coach.planning.allocation import build_deterministic_plan
from ai_interview_coach.tools.research_policy import ResearchAuthorizationError
from ai_interview_coach.tools.research_search import search_once


@pytest.fixture
def session():
    requirements = JobRequirements(
        role="Engineer", seniority="mid", core_skills=["python"], nice_to_have=["docker"]
    )
    return InterviewSession(requirements=requirements, plan=build_deterministic_plan(requirements))


def outcome(status):
    return SearchOutcome(
        status=status,
        snippets=[
            {
                "title": "Python",
                "url": "https://example.com/python",
                "content": "How do Python generators work?",
            }
        ]
        if status == "success"
        else [],
    )


@pytest.mark.parametrize("status", ["success", "empty", "error"])
def test_all_outcomes_are_cached_after_reserving_budget(session, status):
    calls = []

    def search(skill, seniority):
        assert session.search_calls_by_skill[skill] == 1
        calls.append((skill, seniority))
        return outcome(status)

    request = QuestionResearchRequest(skill=" Python ")
    first = search_once(session, request, search=search)
    second = search_once(session, request, search=search)
    assert first == second == outcome(status)
    assert len(calls) == 1
    assert session.activity_log[-1].metadata["cache_hit"] is True


def test_unexpected_error_is_cached_before_propagating(session):
    calls = []

    def broken(*args):
        calls.append(args)
        raise RuntimeError("Programming failure")

    request = QuestionResearchRequest(skill="python")
    with pytest.raises(RuntimeError):
        search_once(session, request, search=broken)
    assert search_once(session, request, search=broken).status == "error"
    assert len(calls) == 1


@pytest.mark.parametrize("skill", ["docker", "java", "behavioral"])
def test_unauthorized_requests_never_call_search(session, skill):
    def forbidden(*args):
        pytest.fail("Search must not run")

    with pytest.raises(ResearchAuthorizationError):
        search_once(session, QuestionResearchRequest(skill=skill), search=forbidden)
    assert session.search_calls_by_skill == {}


def test_seniority_change_does_not_grant_new_allowance(session):
    calls = []

    def search(*args):
        calls.append(args)
        return outcome("empty")

    request = QuestionResearchRequest(skill="python")
    search_once(session, request, search=search)
    session.requirements = JobRequirements(
        role="Engineer", seniority="senior", core_skills=["python"]
    )
    session.plan = build_deterministic_plan(session.requirements)
    assert search_once(session, request, search=search).status == "error"
    assert len(calls) == 1


def test_sessions_do_not_share_search_budgets(session):
    other = InterviewSession(
        requirements=session.requirements.model_copy(deep=True),
        plan=session.plan.model_copy(deep=True),
    )
    calls = []

    def search(*args):
        calls.append(args)
        return outcome("empty")

    request = QuestionResearchRequest(skill="python")
    search_once(session, request, search=search)
    search_once(other, request, search=search)
    assert len(calls) == 2


def test_invalid_return_leaves_error_cached(session):
    malformed = SearchOutcome.model_construct(status=SearchStatus.SUCCESS, snippets=[])
    request = QuestionResearchRequest(skill="python")
    with pytest.raises(ValidationError):
        search_once(session, request, search=lambda *_: malformed)
    assert session.search_cache[("python", session.requirements.seniority)].status == "error"


def test_missing_plan_blocks_search(session):
    session.plan = None
    with pytest.raises(ResearchAuthorizationError):
        search_once(session, QuestionResearchRequest(skill="python"), search=lambda *_: None)
