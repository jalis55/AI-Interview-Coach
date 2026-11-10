"""Bounded model calls with explicit accounting, JSON fallback, and safe exhaustion."""

from dataclasses import dataclass

from groq import APIConnectionError, APIStatusError, InternalServerError
from langchain_core.exceptions import OutputParserException

from ai_interview_coach.services.research import groq_diagnostics
from ai_interview_coach.utils.activity import emit
from ai_interview_coach.utils.usage import model_config


@dataclass(frozen=True)
class ValidatedCall[T]:
    value: T | None
    primary_attempts: int
    fallback_attempts: int


def call_validated(session, primary, fallback, inputs, schema, settings, *, stage, output_key=None):
    counts = {"primary": 0, "fallback": 0}
    for phase, chain, limit in (
        ("primary", primary, settings.primary_max_attempts),
        ("fallback", fallback, settings.fallback_max_attempts),
    ):
        if phase == "fallback":
            emit(session, "fallback_started", stage=stage)
        for attempt in range(1, limit + 1):
            counts[phase] += 1
            emit(session, f"{phase}_attempt", stage=stage, attempt=attempt)
            if attempt > 1:
                emit(session, "retry", stage=stage, attempt=attempt)
            try:
                raw = chain.invoke(inputs, config=model_config(session, stage))
                if output_key:
                    raw = raw[output_key]
                value = schema.model_validate(raw)
            except (APIConnectionError, InternalServerError, OutputParserException, ValueError):
                continue
            except APIStatusError as error:
                emit(
                    session,
                    "provider_unavailable",
                    stage=stage,
                    status="error",
                    **groq_diagnostics(error),
                )
                if phase == "primary" and error.status_code == 400:
                    # A strict JSON prompt can recover unsupported/failed schema responses.
                    break
                if phase == "fallback":
                    emit(session, "fallback_finished", stage=stage, status="error")
                return ValidatedCall(None, counts["primary"], counts["fallback"])
            else:
                if phase == "fallback":
                    emit(session, "fallback_finished", stage=stage)
                return ValidatedCall(value, counts["primary"], counts["fallback"])
        if phase == "fallback":
            emit(session, "fallback_finished", stage=stage, status="error")
    return ValidatedCall(None, counts["primary"], counts["fallback"])
