"""Evaluate one answer using staged history and marked neutral defaults."""

from langchain_core.chat_history import InMemoryChatMessageHistory

from ai_interview_coach.chains.evaluator import build_evaluator, with_staged_history
from ai_interview_coach.models.evaluation import AnswerScore
from ai_interview_coach.models.interview import EvaluationDecision, EvaluationOutcome
from ai_interview_coach.services.validated_call import call_validated
from ai_interview_coach.utils.activity import emit


class EvaluationService:
    def __init__(self, settings, primary, fallback):
        self.settings = settings
        self.primary = primary
        self.fallback = fallback

    def evaluate(self, session, question, answer, history):
        if session.is_demo:
            return self.safe_default(session, demo=True)
        staged = InMemoryChatMessageHistory(messages=list(history.messages))
        primary = with_staged_history(
            self.primary,
            staged,
            self.settings.history_max_messages,
            self.settings.history_max_characters,
        )
        fallback = with_staged_history(
            self.fallback,
            staged,
            self.settings.history_max_messages,
            self.settings.history_max_characters,
        )
        result = call_validated(
            session,
            primary,
            fallback,
            {
                "requirements": session.requirements.model_dump_json(),
                "question": question.model_dump_json(),
                "message": answer,
            },
            EvaluationDecision,
            self.settings,
            stage="evaluation",
            output_key="decision",
        )
        if result.value is None:
            return self.safe_default(session, result.primary_attempts, result.fallback_attempts)
        return EvaluationOutcome(
            decision=result.value,
            defaulted=False,
            primary_attempts=result.primary_attempts,
            fallback_attempts=result.fallback_attempts,
        )

    @staticmethod
    def safe_default(session, primary_attempts=0, fallback_attempts=0, *, demo=False):
        emit(session, "safe_default", stage="evaluation", status="defaulted")
        feedback = (
            "Offline demo: this feedback is simulated and cannot assess your readiness."
            if demo
            else "Sorry, the evaluation service could not reliably assess this answer. "
            "A neutral score of 5 was recorded to preserve progress; it is not evidence of ability."
        )
        return EvaluationOutcome(
            decision=EvaluationDecision(
                status="accepted",
                assessment=AnswerScore(
                    score=5,
                    feedback=feedback,
                    strengths=[],
                    improvements=["Revisit this question when evaluation is available."],
                ),
            ),
            defaulted=True,
            primary_attempts=primary_attempts,
            fallback_attempts=fallback_attempts,
        )


def create_evaluation_service(settings):
    return EvaluationService(settings, build_evaluator(), build_evaluator(fallback=True))
