"""Provider-free workflow fixtures shared by integration tests."""

from types import SimpleNamespace

import pytest
from langchain_core.runnables import RunnableLambda

from ai_interview_coach.config import Settings
from ai_interview_coach.models.evaluation import AnswerScore
from ai_interview_coach.models.interview import EvaluationDecision
from ai_interview_coach.models.job import JobRequirements
from ai_interview_coach.models.plan import Difficulty
from ai_interview_coach.models.question import InterviewQuestion
from ai_interview_coach.models.session import InterviewStatus
from ai_interview_coach.planning.allocation import build_deterministic_plan
from ai_interview_coach.services.evaluation import EvaluationService
from ai_interview_coach.services.interview import InterviewService
from ai_interview_coach.services.reporting import ReportService
from ai_interview_coach.services.research import ResearchPreparationError
from ai_interview_coach.stores.history_store import InMemoryHistoryStore
from ai_interview_coach.stores.lineage_store import InMemoryLineageStore
from ai_interview_coach.stores.session_store import InMemorySessionStore
from ai_interview_coach.tools.generic_questions import generic_question_texts
from ai_interview_coach.tools.question_filter import is_duplicate


@pytest.fixture
def interview_harness():
    settings = Settings(
        _env_file=None,
        groq_api_key="test",
        tavily_api_key="test",
        groq_model="test-model",
        history_max_messages=6,
    )
    sessions, histories, lineages = (
        InMemorySessionStore(),
        InMemoryHistoryStore(),
        InMemoryLineageStore(),
    )
    calls, scores, generated = [], [], []

    def evaluate(inputs):
        calls.append(inputs)
        score = scores.pop(0) if scores else 7
        if isinstance(score, EvaluationDecision):
            return score
        return EvaluationDecision(
            status="accepted",
            assessment=AnswerScore(
                score=score,
                feedback="Explain the trade-off with a concrete example.",
                strengths=["Identifies the main concept."],
                improvements=["Add a practical example."],
            ),
        )

    def generate(session, skill, difficulty):
        generated.append((skill, difficulty))
        exclusions = session.asked_questions + [q.question for q in session.candidate_pool]
        for text in generic_question_texts(skill):
            if not is_duplicate(text, exclusions, skill=skill):
                return [
                    InterviewQuestion(
                        question=text,
                        skill=skill,
                        difficulty=difficulty,
                        source="llm_fallback",
                        rationale="Generic skill practice: test fixture.",
                    )
                ]
        raise ResearchPreparationError("No unused questions remain.")

    evaluator = EvaluationService(settings, RunnableLambda(evaluate), RunnableLambda(evaluate))
    service = InterviewService(
        settings=settings,
        sessions=sessions,
        histories=histories,
        lineages=lineages,
        evaluator=evaluator,
        reporter=ReportService(settings, {}),
        generator=generate,
    )

    def create(skills=None, seniority="mid"):
        session = sessions.create()
        session.requirements = JobRequirements(
            role="Backend Engineer", seniority=seniority, core_skills=skills or ["python", "sql"]
        )
        session.plan = build_deterministic_plan(session.requirements)
        session.research_complete = True
        session.status = InterviewStatus.PREPARING
        difficulty = {
            "junior": Difficulty.EASY,
            "mid": Difficulty.MEDIUM,
            "senior": Difficulty.HARD,
            "staff": Difficulty.HARD,
        }[seniority]
        session.candidate_pool = [
            InterviewQuestion(
                question=text,
                skill=skill,
                difficulty=difficulty,
                source="llm_fallback",
                rationale="Generic skill practice: test fixture.",
            )
            for skill in [*session.requirements.core_skills, "behavioral"]
            for text in generic_question_texts(skill)[:2]
        ]
        return session

    return SimpleNamespace(
        settings=settings,
        sessions=sessions,
        histories=histories,
        lineages=lineages,
        service=service,
        create=create,
        calls=calls,
        scores=scores,
        generated=generated,
    )
