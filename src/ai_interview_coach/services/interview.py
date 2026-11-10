"""Application-owned question display, turn commits, practice, and fresh retries."""

from difflib import SequenceMatcher
from functools import wraps
from uuid import UUID, uuid4

from langchain_core.messages import AIMessage, HumanMessage

from ai_interview_coach.chains.adaptation import build_difficulty_router
from ai_interview_coach.models.interview import (
    EvaluationRecord,
    InterviewProgress,
    PendingEvaluation,
)
from ai_interview_coach.models.plan import QuestionSlot, QuestionType
from ai_interview_coach.models.session import InterviewStatus
from ai_interview_coach.planning.allocation import initial_target_difficulty
from ai_interview_coach.planning.validation import validate_plan_for_requirements
from ai_interview_coach.services.evaluation import create_evaluation_service
from ai_interview_coach.services.reporting import create_report_service
from ai_interview_coach.services.research import ResearchPreparationError, create_research_service
from ai_interview_coach.tools.question_filter import is_duplicate, normalize_text
from ai_interview_coach.utils.activity import emit


class UnrelatedAnswerError(ValueError):
    """The candidate requested an unrelated action; preserve the current turn."""


def session_locked(method):
    """Serialize display/round actions against turn commits in the same process."""

    @wraps(method)
    def wrapped(self, session, *args, **kwargs):
        with self.sessions.lock(session.session_id):
            return method(self, session, *args, **kwargs)

    return wrapped


class InterviewService:
    def __init__(self, *, settings, sessions, histories, lineages, evaluator, reporter, generator):
        self.settings = settings
        self.sessions = sessions
        self.histories = histories
        self.lineages = lineages
        self.evaluator = evaluator
        self.reporter = reporter
        self.generator = generator
        self.router = build_difficulty_router()

    @session_locked
    def start(self, session):
        if session.requirements is None or session.plan is None or not session.research_complete:
            raise ValueError("Confirm requirements, plan coverage, and prepare questions first.")
        session.plan = validate_plan_for_requirements(session.plan, session.requirements)
        if not session.progress.round_slots:
            target = initial_target_difficulty(session.requirements.seniority)
            levels = {skill: target for skill in [*session.requirements.core_skills, "behavioral"]}
            session.progress = InterviewProgress(
                round_slots=[slot.model_copy(deep=True) for slot in session.plan.slots],
                target_difficulty=levels,
                practice_difficulty=dict(levels),
            )
        self.lineages.ensure(session)
        return self.show_question(session)

    def _select_question(self, session, skill, difficulty):
        exclusions = self.lineages.ensure(session).asked_questions
        candidates = [
            q
            for q in session.candidate_pool
            if q.skill == skill
            and q.difficulty == difficulty
            and not is_duplicate(q.question, exclusions, skill=skill)
        ]
        if not candidates:
            candidates = self.generator(session, skill, difficulty)
            candidates = [
                q
                for q in candidates
                if q.skill == skill
                and q.difficulty == difficulty
                and not is_duplicate(q.question, exclusions, skill=skill)
            ]
            if not candidates:
                raise ResearchPreparationError(
                    "No unused question is available. Please retry later."
                )
            unused = [
                q
                for q in session.candidate_pool
                if not is_duplicate(q.question, exclusions, skill=q.skill)
            ]
            session.candidate_pool = (candidates + unused)[: self.settings.candidate_pool_limit]
        previous = [
            r.question.question for r in session.progress.records if r.question.skill == skill
        ]

        def similarity(question):
            return max(
                (
                    SequenceMatcher(
                        None, normalize_text(question.question), normalize_text(text)
                    ).ratio()
                    for text in previous
                ),
                default=0,
            )

        context = set(normalize_text(session.jd_context).split()) - {
            "the",
            "a",
            "an",
            "in",
            "and",
            "or",
            "of",
            "to",
            "with",
            "you",
            "how",
            "would",
        }

        def priority(question):
            words = set(normalize_text(question.question).split())
            relevance = len(words & context) / max(1, len(words))
            return (-relevance, similarity(question))

        return min(candidates, key=priority).model_copy(deep=True)

    @session_locked
    def show_question(self, session):
        progress = session.progress
        if progress.current_question is not None:
            self.lineages.mark_displayed(session, progress.current_question)
            self._sync_history(session)
            return progress.current_question
        if progress.current_index >= len(progress.round_slots):
            return None
        slot = progress.round_slots[progress.current_index]
        difficulty = progress.practice_difficulty[slot.skill]
        try:
            question = self._select_question(session, slot.skill, difficulty)
        except ResearchPreparationError:
            session.status = InterviewStatus.RECOVERABLE_ERROR
            raise
        updated = progress.model_copy(deep=True)
        updated.current_question = question
        updated.current_turn_id = uuid4()
        session.progress = InterviewProgress.model_validate(updated.model_dump())
        self.lineages.mark_displayed(session, question)
        session.status = InterviewStatus.AWAITING_ANSWER
        self._sync_history(session)
        emit(
            session,
            "question_displayed",
            stage="interview",
            skill=question.skill,
            source=question.source.value,
            count=progress.current_index + 1,
        )
        return question

    def _sync_history(self, session):
        messages = []
        for record in session.progress.records:
            messages.extend(
                [
                    AIMessage(content=record.question.question),
                    HumanMessage(content=record.answer),
                    AIMessage(content=record.assessment.feedback),
                ]
            )
        if session.progress.current_question is not None:
            messages.append(AIMessage(content=session.progress.current_question.question))
        history = self.histories.get(session.session_id)
        history.clear()
        history.add_messages(messages[-self.settings.history_max_messages :])

    def submit(self, session, *, answer, turn_id):
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Enter an answer before submitting.")
        cleaned = answer.strip()
        if len(cleaned) > self.settings.max_answer_characters:
            raise ValueError("The answer is too long. Please shorten it.")
        turn_id = UUID(str(turn_id))
        lock = self.sessions.lock(session.session_id)
        if not lock.acquire(blocking=False):
            raise ValueError("An answer is already being processed.")
        try:
            for record in session.progress.records:
                if record.turn_id == turn_id:
                    if record.answer != cleaned:
                        raise ValueError("This turn was already processed with a different answer.")
                    self._sync_history(session)
                    return record
            progress = session.progress
            if (
                progress.current_turn_id != turn_id
                or progress.current_question is None
                or session.status == InterviewStatus.EVALUATING
            ):
                raise ValueError("This question is no longer accepting that submission.")
            session.status = InterviewStatus.EVALUATING
            try:
                pending = session.pending_evaluations.get(turn_id)
                if pending is not None:
                    if pending.answer != cleaned:
                        raise ValueError("Retry this turn with the original submitted answer.")
                    outcome = pending.outcome
                else:
                    outcome = self.evaluator.evaluate(
                        session,
                        progress.current_question,
                        cleaned,
                        self.histories.get(session.session_id),
                    )
                    if outcome.decision.status == "unrelated":
                        raise UnrelatedAnswerError(
                            "Please return to answering the interview question."
                        )
                    session.pending_evaluations[turn_id] = PendingEvaluation(
                        answer=cleaned,
                        outcome=outcome,
                    )
                record = EvaluationRecord(
                    turn_id=turn_id,
                    round_id=progress.round_id,
                    question=progress.current_question.model_copy(deep=True),
                    answer=cleaned,
                    assessment=outcome.decision.assessment,
                    evaluation_status="defaulted" if outcome.defaulted else "valid",
                    primary_attempts=outcome.primary_attempts,
                    fallback_attempts=outcome.fallback_attempts,
                )
                updated = progress.model_copy(deep=True)
                updated.records.append(record)
                updated.processed_turn_ids.add(turn_id)
                updated.covered_skills.add(record.question.skill)
                updated.practice_difficulty[record.question.skill] = self.router.invoke(
                    {
                        "score": record.assessment.score,
                        "status": record.evaluation_status,
                        "current": updated.practice_difficulty[record.question.skill],
                    }
                )
                updated.current_index += 1
                updated.current_question = None
                updated.current_turn_id = None
                # Validate the entire ledger, then replace it once: no half-committed turn.
                session.progress = InterviewProgress.model_validate(updated.model_dump())
                session.pending_evaluations.pop(turn_id, None)
                self._sync_history(session)
                emit(
                    session,
                    "answer_committed",
                    stage="interview",
                    skill=record.question.skill,
                    status=record.evaluation_status,
                    count=updated.current_index,
                )
                if updated.current_index == len(updated.round_slots):
                    session.status = InterviewStatus.COMPLETED
                    self.complete_report(session)
                else:
                    session.status = InterviewStatus.AWAITING_ANSWER
                return record
            except UnrelatedAnswerError:
                session.status = InterviewStatus.AWAITING_ANSWER
                raise
            except Exception:
                session.status = InterviewStatus.RECOVERABLE_ERROR
                raise
        finally:
            lock.release()

    @session_locked
    def complete_report(self, session):
        if session.final_report is None:
            session.final_report = self.reporter.create(session)
            session.report_history.append(session.final_report.model_copy(deep=True))
            emit(session, "report_ready", stage="report", count=len(session.progress.records))
        session.status = InterviewStatus.COMPLETED
        return session.final_report

    @staticmethod
    def weak_skills(session):
        report = session.final_report
        if report is None:
            return []
        evidence = sorted(
            report.coverage,
            key=lambda e: (
                e.reliable_mean is not None,
                e.reliable_mean or 0,
                e.valid_count,
            ),
        )
        weak = [
            e.skill
            for e in evidence
            if e.valid_count < 2
            or e.reliable_mean is None
            or e.reliable_mean < 7
            or "No reliable" in e.target_gap
            or "need improvement" in e.target_gap
        ]
        return weak or [e.skill for e in evidence]

    @session_locked
    def start_practice(self, session, *, count, skills):
        if session.status != InterviewStatus.COMPLETED or session.final_report is None:
            raise ValueError("Complete the current round before starting practice.")
        if type(count) is not int or count not in {3, 5, 10}:
            raise ValueError("Practice size must be 3, 5, or 10.")
        allowed = set(self.weak_skills(session))
        selected = list(dict.fromkeys(skills))
        if not selected or not set(selected) <= allowed:
            raise ValueError("Select at least one skill from the report's practice suggestions.")
        updated = session.progress.model_copy(deep=True)
        updated.round_id = uuid4()
        updated.round_kind = "practice"
        updated.current_index = 0
        updated.current_question = None
        updated.current_turn_id = None
        updated.round_slots = [
            QuestionSlot(
                skill=selected[i % len(selected)],
                question_type=QuestionType.BEHAVIORAL
                if selected[i % len(selected)] == "behavioral"
                else QuestionType.TECHNICAL,
                target_difficulty=updated.target_difficulty[selected[i % len(selected)]],
            )
            for i in range(count)
        ]
        session.progress = InterviewProgress.model_validate(updated.model_dump())
        session.final_report = None
        session.status = InterviewStatus.AWAITING_ANSWER
        emit(session, "practice_started", stage="practice", count=count)
        return self.show_question(session)

    @session_locked
    def fresh_retry(self, session):
        lineage = self.lineages.ensure(session)
        fresh = self.sessions.create()
        fresh.requirements = lineage.requirements.model_copy(deep=True)
        fresh.jd_context = lineage.jd_context
        fresh.jd_id = session.jd_id
        fresh.lineage_id = session.lineage_id
        fresh.asked_questions = list(lineage.asked_questions)
        fresh.plan = session.plan.model_copy(deep=True) if session.plan else None
        fresh.status = InterviewStatus.READY if fresh.plan else InterviewStatus.DRAFT
        fresh.is_demo = session.is_demo
        self.histories.get(fresh.session_id)
        emit(fresh, "fresh_retry", stage="retry", count=len(fresh.asked_questions))
        return fresh


def create_interview_service(settings, sessions, histories, lineages):
    research = create_research_service(settings)
    return InterviewService(
        settings=settings,
        sessions=sessions,
        histories=histories,
        lineages=lineages,
        evaluator=create_evaluation_service(settings),
        reporter=create_report_service(settings),
        generator=research.generate_for_turn,
    )
