"""Failure honesty, fallback bounds, and evidence-aware reporting."""

from statistics import fmean

import httpx
import pytest
from groq import BadRequestError, RateLimitError
from langchain_core.runnables import RunnableLambda

from ai_interview_coach.models.interview import EvaluationDecision
from ai_interview_coach.models.plan import Difficulty
from ai_interview_coach.models.report import ReportText
from ai_interview_coach.services.evaluation import EvaluationService
from ai_interview_coach.services.reporting import ReportService


def finish(h, session):
    if not session.progress.round_slots:
        h.service.start(session)
    while session.progress.current_index < len(session.progress.round_slots):
        h.service.show_question(session)
        h.service.submit(session, answer="My answer", turn_id=session.progress.current_turn_id)


def test_invalid_evaluations_exhaust_three_plus_two_and_default_without_adaptation(
    interview_harness,
):
    h = interview_harness
    calls = []

    def malformed(values):
        calls.append(values)
        return {
            "status": "accepted",
            "assessment": {
                "score": "9",
                "feedback": "Invalid type",
                "strengths": [],
                "improvements": [],
            },
        }

    h.service.evaluator = EvaluationService(
        h.settings, RunnableLambda(malformed), RunnableLambda(malformed)
    )
    session = h.create()
    h.service.start(session)
    record = h.service.submit(session, answer="Answer", turn_id=session.progress.current_turn_id)
    assert len(calls) == 5
    assert record.primary_attempts == 3
    assert record.fallback_attempts == 2
    assert record.evaluation_status == "defaulted"
    assert record.assessment.score == 5
    assert session.progress.practice_difficulty["python"] is Difficulty.MEDIUM
    assert len(h.histories.get(session.session_id).messages) == 3


def test_schema_http_400_uses_json_fallback_without_repeating_primary(interview_harness):
    h = interview_harness
    counts = [0, 0]

    def primary(values):
        counts[0] += 1
        raise BadRequestError(
            "Schema failed",
            response=httpx.Response(400, request=httpx.Request("POST", "https://api.groq.com")),
            body={"code": "json_validate_failed"},
        )

    def fallback(values):
        counts[1] += 1
        return EvaluationDecision(
            status="accepted",
            assessment={
                "score": 8,
                "feedback": "Correct",
                "strengths": ["Clear"],
                "improvements": [],
            },
        )

    h.service.evaluator = EvaluationService(
        h.settings, RunnableLambda(primary), RunnableLambda(fallback)
    )
    session = h.create()
    h.service.start(session)
    record = h.service.submit(session, answer="Answer", turn_id=session.progress.current_turn_id)
    assert counts == [1, 1]
    assert record.evaluation_status == "valid"
    assert record.primary_attempts == record.fallback_attempts == 1


def test_rate_limit_stops_without_json_retry_and_report_discloses_all_defaults(interview_harness):
    h = interview_harness
    calls = []

    def unavailable(values):
        calls.append(values)
        raise RateLimitError(
            "Rate limited",
            response=httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com")),
            body=None,
        )

    failing = RunnableLambda(unavailable)
    h.service.evaluator = EvaluationService(h.settings, failing, failing)
    session = h.create()
    finish(h, session)
    assert len(calls) == 3
    assert session.final_report.overall_score == 5
    assert session.final_report.defaulted_count == 3
    assert session.final_report.readiness_status == "unavailable"
    assert all(e.valid_count == 0 for e in session.final_report.coverage)
    assert "3 neutral fallback" in session.final_report.caveat


def test_report_includes_defaulted_scores_in_mean_but_not_reliable_skill_evidence(
    interview_harness,
):
    h = interview_harness
    session = h.create()
    h.scores.extend([3, 9, 8])
    finish(h, session)
    session.progress.records[1].evaluation_status = "defaulted"
    session.progress.records[1].assessment.score = 5
    report = h.service.reporter.create(session)
    assert report.overall_score == fmean([3, 5, 8])
    assert report.defaulted_count == 1
    sql = next(e for e in report.coverage if e.skill == "sql")
    assert sql.valid_count == 0
    assert sql.reliable_mean is None
    assert sql.observations[0].status == "defaulted"


def test_parallel_report_branch_failure_preserves_average_and_other_branches(interview_harness):
    h = interview_harness
    session = h.create()
    finish(h, session)

    def explode(values):
        raise RuntimeError("Unexpected branch failure")

    branches = {
        "strengths_summary": (RunnableLambda(explode), RunnableLambda(explode)),
        "gaps_summary": (
            RunnableLambda(lambda _: ReportText(text="Specific observed gap.")),
            RunnableLambda(explode),
        ),
    }
    report = ReportService(h.settings, branches).create(session)
    assert report.overall_score == 7
    assert report.gaps_summary == "Specific observed gap."
    assert report.strengths_summary
    assert report.recommendations


def test_easy_high_scores_do_not_erase_senior_target_gap(interview_harness):
    h = interview_harness
    session = h.create(seniority="senior")
    finish(h, session)
    python = next(r for r in session.progress.records if r.question.skill == "python")
    python.question.difficulty = Difficulty.EASY
    python.assessment.score = 9
    report = h.service.reporter.create(session)
    evidence = next(e for e in report.coverage if e.skill == "python")
    assert evidence.target_difficulty is Difficulty.HARD
    assert evidence.reliable_mean == 9
    assert "No reliable" in evidence.target_gap
    assert evidence.assessment == "insufficiently_assessed"


def test_omitted_skills_are_reported_and_can_be_practiced_without_new_search(interview_harness):
    h = interview_harness
    skills = [f"skill_{i}" for i in range(10)]
    session = h.create(skills)
    finish(h, session)
    assert session.final_report.omitted_skills == ["skill_9"]
    omitted = next(e for e in session.final_report.coverage if e.skill == "skill_9")
    assert omitted.observations == []
    h.service.start_practice(session, count=3, skills=["skill_9"])
    assert session.progress.current_question.skill == "skill_9"
    assert session.search_calls_by_skill == {}


def test_practice_rejects_invalid_size_or_unauthorized_skills(interview_harness):
    h = interview_harness
    session = h.create()
    finish(h, session)
    for count, skills in [(2, ["python"]), (True, ["python"]), (3, []), (3, ["java"])]:
        with pytest.raises(ValueError):
            h.service.start_practice(session, count=count, skills=skills)


def test_staged_history_is_bounded_by_characters_without_mutating_committed_history(
    interview_harness,
):
    from langchain_core.messages import HumanMessage

    h = interview_harness
    h.settings.history_max_characters = 1000
    session = h.create()
    question = h.service.start(session)
    history = h.histories.get(session.session_id)
    history.add_messages([HumanMessage(content="private history " * 500) for _ in range(5)])
    original = [m.content for m in history.messages]
    h.service.evaluator.evaluate(session, question, "Answer", history)
    assert sum(len(m.content) for m in h.calls[-1]["history"]) <= 1000
    assert [m.content for m in history.messages] == original
