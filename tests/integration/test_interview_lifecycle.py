"""Turns, report completion, adaptation, practice, and retry lineage."""

from statistics import fmean
from threading import Event, Thread

import pytest
from langchain_core.runnables import RunnableLambda

from ai_interview_coach.models.interview import EvaluationDecision
from ai_interview_coach.models.plan import Difficulty
from ai_interview_coach.models.session import InterviewStatus
from ai_interview_coach.services.interview import UnrelatedAnswerError


def complete(h, session):
    if not session.progress.round_slots:
        h.service.start(session)
    while session.progress.current_index < len(session.progress.round_slots):
        h.service.show_question(session)
        h.service.submit(
            session,
            answer="A concise explanation with a concrete example.",
            turn_id=session.progress.current_turn_id,
        )


def test_question_display_is_stable_and_records_exclusions_immediately(interview_harness):
    h = interview_harness
    session = h.create()
    first = h.service.start(session)
    turn = session.progress.current_turn_id
    assert h.service.show_question(session) == first
    assert session.progress.current_turn_id == turn
    assert session.asked_questions == [first.question]
    assert h.lineages.ensure(session).asked_questions == [first.question]
    assert len(h.histories.get(session.session_id).messages) == 1
    assert h.calls == []


def test_duplicate_submission_reuses_record_without_scoring_or_progress_twice(interview_harness):
    h = interview_harness
    session = h.create()
    h.service.start(session)
    turn = session.progress.current_turn_id
    first = h.service.submit(session, answer="My answer", turn_id=turn)
    second = h.service.submit(session, answer="My answer", turn_id=turn)
    assert first == second
    assert len(h.calls) == 1
    assert session.progress.current_index == 1
    assert len(session.progress.records) == 1
    assert len(h.histories.get(session.session_id).messages) == 3
    with pytest.raises(ValueError, match="different answer"):
        h.service.submit(session, answer="Changed answer", turn_id=turn)


def test_empty_and_stale_submissions_do_not_call_evaluator(interview_harness):
    from uuid import uuid4

    h = interview_harness
    session = h.create()
    h.service.start(session)
    with pytest.raises(ValueError, match="Enter an answer"):
        h.service.submit(session, answer="   ", turn_id=session.progress.current_turn_id)
    with pytest.raises(ValueError, match="no longer"):
        h.service.submit(session, answer="Answer", turn_id=uuid4())
    assert session.progress.current_index == 0
    assert h.calls == []


def test_unrelated_request_preserves_turn_and_does_not_pollute_history(interview_harness):
    h = interview_harness
    session = h.create()
    h.service.start(session)
    turn = session.progress.current_turn_id
    h.scores.append(EvaluationDecision(status="unrelated", assessment=None))
    with pytest.raises(UnrelatedAnswerError):
        h.service.submit(session, answer="Write a cake recipe", turn_id=turn)
    assert session.progress.current_index == 0
    assert session.progress.current_turn_id == turn
    assert len(h.histories.get(session.session_id).messages) == 1
    h.service.submit(session, answer="Now answering the actual question", turn_id=turn)
    assert session.progress.current_index == 1
    assert len(h.calls) == 2


def test_adaptation_changes_only_evaluated_skill_and_keeps_target_fixed(interview_harness):
    h = interview_harness
    h.scores.append(3)
    session = h.create()
    h.service.start(session)
    h.service.submit(session, answer="Partial answer", turn_id=session.progress.current_turn_id)
    assert session.progress.practice_difficulty["python"] is Difficulty.EASY
    assert session.progress.practice_difficulty["sql"] is Difficulty.MEDIUM
    assert session.progress.target_difficulty["python"] is Difficulty.MEDIUM


def test_full_round_produces_exact_report_only_at_completion(interview_harness):
    h = interview_harness
    session = h.create()
    h.service.start(session)
    with pytest.raises(ValueError, match="completed round"):
        h.service.complete_report(session)
    h.scores.extend([3, 9, 8])
    complete(h, session)
    report = session.final_report
    assert report.overall_score == fmean([3, 9, 8])
    assert report.defaulted_count == 0
    assert report.readiness_status == "limited_evidence"
    assert all(e.assessment == "insufficiently_assessed" for e in report.coverage)
    assert session.status is InterviewStatus.COMPLETED
    assert len(session.report_history) == 1
    assert h.service.complete_report(session) == report
    assert len(session.report_history) == 1


@pytest.mark.parametrize("size", [3, 5, 10])
def test_focused_practice_reuses_budget_and_preserves_targets(interview_harness, size):
    h = interview_harness
    session = h.create()
    session.search_calls_by_skill = {"python": 1, "sql": 1}
    complete(h, session)
    target = dict(session.progress.target_difficulty)
    old_round = session.progress.round_id
    h.service.start_practice(session, count=size, skills=["python"])
    assert len(session.progress.round_slots) == size
    assert session.progress.round_id != old_round
    complete(h, session)
    assert len(session.progress.records) == 3 + size
    assert session.progress.target_difficulty == target
    assert session.search_calls_by_skill == {"python": 1, "sql": 1}
    assert session.final_report.evaluated_count == 3 + size
    assert len(session.report_history) == 2
    assert len(session.asked_questions) == len(set(session.asked_questions))


def test_fresh_retry_excludes_displayed_but_unanswered_questions(interview_harness):
    h = interview_harness
    session = h.create()
    question = h.service.start(session)
    fresh = h.service.fresh_retry(session)
    assert fresh.session_id != session.session_id
    assert fresh.lineage_id == session.lineage_id
    assert fresh.jd_id == session.jd_id
    assert fresh.requirements == session.requirements
    assert fresh.progress.records == []
    assert fresh.search_calls_by_skill == fresh.search_cache == {}
    assert h.histories.get(fresh.session_id).messages == []
    assert question.question in fresh.asked_questions
    fresh.research_complete = True
    assert h.service.start(fresh).question != question.question


def test_bounded_history_and_separate_sessions(interview_harness):
    h = interview_harness
    first, second = h.create(), h.create()
    complete(h, first)
    assert len(h.histories.get(first.session_id).messages) <= h.settings.history_max_messages
    assert h.histories.get(second.session_id).messages == []
    assert second.progress.records == []
    assert second.asked_questions == []
    assert second.lineage_id != first.lineage_id


def test_saved_evaluation_survives_commit_failure_without_repeating_provider_call(
    interview_harness,
    monkeypatch,
):
    h = interview_harness
    session = h.create()
    h.service.start(session)
    turn = session.progress.current_turn_id
    original = h.service.router
    h.service.router = RunnableLambda(
        lambda _: (_ for _ in ()).throw(RuntimeError("commit failure"))
    )
    with pytest.raises(RuntimeError):
        h.service.submit(session, answer="Answer", turn_id=turn)
    assert turn in session.pending_evaluations
    assert session.progress.current_index == 0
    h.service.router = original
    h.service.submit(session, answer="Answer", turn_id=turn)
    assert len(h.calls) == 1
    assert session.progress.current_index == 1
    assert session.pending_evaluations == {}


def test_concurrent_submit_does_not_evaluate_twice(interview_harness):
    h = interview_harness
    session = h.create()
    h.service.start(session)
    turn = session.progress.current_turn_id
    entered, release = Event(), Event()
    original = h.service.evaluator.evaluate
    failures = []

    def delayed(*args):
        entered.set()
        assert release.wait(timeout=5)
        return original(*args)

    h.service.evaluator.evaluate = delayed

    def submit():
        try:
            h.service.submit(session, answer="Answer", turn_id=turn)
        except Exception as error:
            failures.append(error)

    worker = Thread(target=submit)
    worker.start()
    assert entered.wait(timeout=5)
    try:
        with pytest.raises(ValueError, match="already being processed"):
            h.service.submit(session, answer="Answer", turn_id=turn)
    finally:
        release.set()
        worker.join(timeout=5)
    assert not failures
    assert len(h.calls) == 1
    assert session.progress.current_index == 1


def test_concurrent_question_display_selects_only_once(interview_harness):
    h = interview_harness
    session = h.create()
    session.candidate_pool = []
    entered, release = Event(), Event()
    original = h.service.generator
    calls, results, errors = [], [], []

    def delayed(*args):
        calls.append(1)
        entered.set()
        assert release.wait(timeout=5)
        return original(*args)

    h.service.generator = delayed

    def display(start=False):
        try:
            results.append(h.service.start(session) if start else h.service.show_question(session))
        except Exception as error:
            errors.append(error)

    first = Thread(target=lambda: display(True))
    second = Thread(target=display)
    first.start()
    assert entered.wait(timeout=5)
    second.start()
    release.set()
    first.join(timeout=5)
    second.join(timeout=5)
    assert not errors
    assert len(results) == 2
    assert results[0].id == results[1].id
    assert len(calls) == 1
    assert len(session.asked_questions) == 1
