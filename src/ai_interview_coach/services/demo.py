"""Reproducible, visibly simulated demo without provider invocations."""

from ai_interview_coach.models.job import JobRequirements
from ai_interview_coach.models.plan import Difficulty
from ai_interview_coach.models.question import InterviewQuestion
from ai_interview_coach.models.session import InterviewStatus
from ai_interview_coach.planning.allocation import build_deterministic_plan
from ai_interview_coach.tools.generic_questions import generic_question_texts


def load_demo(session):
    session.is_demo = True
    session.requirements = JobRequirements(
        role="Backend Engineer",
        seniority="mid",
        core_skills=["python", "sql"],
    )
    session.jd_context = "Offline demo: backend development using Python and SQL."
    session.plan = build_deterministic_plan(session.requirements)
    session.research_complete = True
    session.status = InterviewStatus.PREPARING
    session.candidate_pool = [
        InterviewQuestion(
            question=text,
            skill=skill,
            difficulty=Difficulty.MEDIUM,
            source="llm_fallback",
            rationale="Offline demo: generic practice question.",
        )
        for skill in ["python", "sql", "behavioral"]
        for text in generic_question_texts(skill)[:2]
    ]
    return session
