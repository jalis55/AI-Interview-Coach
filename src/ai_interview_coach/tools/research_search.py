"""Sequential session-scoped caching and one-invocation-per-skill policy."""

from collections.abc import Callable

from ai_interview_coach.models.job import Seniority
from ai_interview_coach.models.research import QuestionResearchRequest, SearchOutcome
from ai_interview_coach.models.session import InterviewSession
from ai_interview_coach.tools.research_policy import (
    ResearchAuthorizationError,
    authorize_research_request,
)
from ai_interview_coach.utils.activity import emit


def search_once(
    session: InterviewSession,
    request: QuestionResearchRequest,
    *,
    search: Callable[[str, Seniority], SearchOutcome],
) -> SearchOutcome:
    if session.requirements is None or session.plan is None:
        raise ResearchAuthorizationError("Confirmed requirements and a plan are required.")
    skill = authorize_research_request(
        request,
        requirements=session.requirements,
        plan=session.plan,
    )
    seniority = session.requirements.seniority
    key = (skill, seniority)
    if key in session.search_cache:
        outcome = session.search_cache[key]
        emit(
            session,
            "search_cache",
            skill=skill,
            cache_hit=True,
            result_count=len(outcome.snippets),
            status=outcome.status.value,
            **search_diagnostics(outcome),
        )
        return outcome
    if session.search_calls_by_skill.get(skill, 0) >= 1:
        outcome = SearchOutcome(status="error")
        session.search_cache[key] = outcome
        emit(session, "search_budget_used", skill=skill, cache_hit=False, status="error")
        return outcome
    session.search_calls_by_skill[skill] = 1
    session.search_cache[key] = SearchOutcome(status="error")
    emit(session, "search_started", skill=skill, cache_hit=False)
    # A raised unexpected error leaves the provisional error cached and propagates.
    try:
        output = search(skill, seniority)
    except Exception:
        emit(session, "search_finished", skill=skill, status="error", result_count=0)
        raise
    outcome = SearchOutcome.model_validate(output.model_dump())
    session.search_cache[key] = outcome
    emit(
        session,
        "search_finished",
        skill=skill,
        cache_hit=False,
        result_count=len(outcome.snippets),
        status=outcome.status.value,
        **search_diagnostics(outcome),
    )
    return outcome


def search_diagnostics(outcome: SearchOutcome) -> dict[str, str | int]:
    metadata: dict[str, str | int] = {"provider": "tavily"}
    if outcome.http_status is not None:
        metadata["http_status"] = outcome.http_status
    if outcome.error_category is not None:
        metadata["error_category"] = outcome.error_category
    return metadata
