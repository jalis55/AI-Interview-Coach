"""Coordinate bounded primary and fallback JD parsing."""

from dataclasses import dataclass

from groq import (
    APIConnectionError,
    APIStatusError,
    InternalServerError,
    RateLimitError,
)
from langchain_core.exceptions import OutputParserException
from langchain_core.runnables import Runnable
from pydantic import ValidationError

from ai_interview_coach.models.jd_parse import JDParseResult
from ai_interview_coach.utils.reliability import run_bounded_attempts

RETRYABLE_ERRORS = (
    APIConnectionError,
    InternalServerError,
    OutputParserException,
    ValidationError,
)


class JDParsingError(RuntimeError):
    """A provider failure that should be shown safely to the candidate."""


@dataclass(frozen=True)
class JDParsingOutcome:
    result: JDParseResult
    primary_attempts: int
    fallback_attempts: int
    exhausted: bool = False


class JDParsingService:
    def __init__(
        self,
        primary: Runnable,
        fallback: Runnable,
        *,
        primary_max_attempts: int = 3,
        fallback_max_attempts: int = 2,
    ) -> None:
        if not 1 <= primary_max_attempts <= 3:
            raise ValueError("Primary attempts must be between 1 and 3.")

        if not 1 <= fallback_max_attempts <= 2:
            raise ValueError("Fallback attempts must be between 1 and 2.")

        self._primary = primary
        self._fallback = fallback
        self._primary_max_attempts = primary_max_attempts
        self._fallback_max_attempts = fallback_max_attempts

    @staticmethod
    def _invoke(chain: Runnable, jd_text: str) -> JDParseResult:
        output = chain.invoke({"jd_text": jd_text})
        return JDParseResult.model_validate(output)

    def parse(self, jd_text: str) -> JDParsingOutcome:
        if not isinstance(jd_text, str):
            raise ValueError("Job description must be text.")

        cleaned = jd_text.strip()

        if not cleaned or len(cleaned) > 30_000:
            return JDParsingOutcome(
                result=JDParseResult(
                    status="needs_correction",
                    requirements=None,
                    message=("Please provide a job description between 1 and 30,000 characters."),
                ),
                primary_attempts=0,
                fallback_attempts=0,
            )

        try:
            primary = run_bounded_attempts(
                lambda: self._invoke(self._primary, cleaned),
                max_attempts=self._primary_max_attempts,
                retry_on=RETRYABLE_ERRORS,
            )

            if primary.succeeded:
                assert primary.value is not None
                return JDParsingOutcome(
                    result=primary.value,
                    primary_attempts=primary.attempts,
                    fallback_attempts=0,
                )

            fallback = run_bounded_attempts(
                lambda: self._invoke(self._fallback, cleaned),
                max_attempts=self._fallback_max_attempts,
                retry_on=RETRYABLE_ERRORS,
            )

            if fallback.succeeded:
                assert fallback.value is not None
                return JDParsingOutcome(
                    result=fallback.value,
                    primary_attempts=primary.attempts,
                    fallback_attempts=fallback.attempts,
                )

        except RateLimitError:
            raise JDParsingError(
                "The model provider is rate-limited. Please try again later."
            ) from None
        except APIStatusError:
            raise JDParsingError(
                "The model provider rejected the request. "
                "Check your credentials, model access, and request configuration."
            ) from None

        return JDParsingOutcome(
            result=JDParseResult(
                status="needs_correction",
                requirements=None,
                message=(
                    "We could not reliably analyze your job description. "
                    "Please try again or provide a clearer description."
                ),
            ),
            primary_attempts=primary.attempts,
            fallback_attempts=fallback.attempts,
            exhausted=True,
        )
