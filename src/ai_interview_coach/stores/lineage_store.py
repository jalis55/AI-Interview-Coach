"""Confirmed JD and displayed-question exclusions across fresh retries."""

from uuid import UUID

from pydantic import BaseModel, Field

from ai_interview_coach.models.job import JobRequirements


class InterviewLineage(BaseModel):
    requirements: JobRequirements
    jd_context: str
    asked_questions: list[str] = Field(default_factory=list)


class InMemoryLineageStore:
    def __init__(self):
        self._lineages: dict[UUID, InterviewLineage] = {}

    def ensure(self, session) -> InterviewLineage:
        if session.requirements is None:
            raise ValueError("Confirmed requirements are required.")
        if session.lineage_id not in self._lineages:
            self._lineages[session.lineage_id] = InterviewLineage(
                requirements=session.requirements.model_copy(deep=True),
                jd_context=session.jd_context,
                asked_questions=list(session.asked_questions),
            )
        return self._lineages[session.lineage_id]

    def mark_displayed(self, session, question):
        lineage = self.ensure(session)
        if question.question not in lineage.asked_questions:
            lineage.asked_questions.append(question.question)
        if question.question not in session.asked_questions:
            session.asked_questions.append(question.question)
