"""JD parsing service tests using fake LCEL runnables."""

import httpx
import pytest
from groq import APIConnectionError, AuthenticationError, RateLimitError
from langchain_core.runnables import RunnableLambda

from ai_interview_coach.models.jd_parse import JDParseResult
from ai_interview_coach.services.jd_parser import JDParsingError, JDParsingService


def correction_result() -> JDParseResult:
    return JDParseResult(
        status="needs_correction",
        requirements=None,
        message="Please provide the role and required skills.",
    )


def valid_result() -> JDParseResult:
    return JDParseResult(
        status="valid",
        requirements={
            "role": "Backend Engineer",
            "seniority": "mid",
            "core_skills": ["python", "sql"],
            "nice_to_have": [],
        },
        message="Please review the extracted requirements.",
    )


def fake_chain(outputs):
    """Return queued outputs and record every invocation."""
    pending = iter(outputs)
    calls = []

    def invoke(inputs):
        calls.append(inputs)
        return next(pending)

    return RunnableLambda(invoke), calls


def test_primary_success_skips_fallback():
    primary, primary_calls = fake_chain([valid_result()])
    fallback, fallback_calls = fake_chain([])

    outcome = JDParsingService(primary, fallback).parse("Example JD")

    assert outcome.result.status == "valid"
    assert outcome.primary_attempts == 1
    assert outcome.fallback_attempts == 0
    assert not outcome.exhausted
    assert len(primary_calls) == 1
    assert fallback_calls == []


def test_correction_returns_without_retry():
    primary, primary_calls = fake_chain([correction_result()])
    fallback, fallback_calls = fake_chain([])

    outcome = JDParsingService(primary, fallback).parse("Unrelated text")

    assert outcome.result.status == "needs_correction"
    assert outcome.primary_attempts == 1
    assert not outcome.exhausted
    assert len(primary_calls) == 1
    assert fallback_calls == []


def test_invalid_primary_output_retries_then_succeeds():
    primary, primary_calls = fake_chain([{}, valid_result()])
    fallback, fallback_calls = fake_chain([])

    outcome = JDParsingService(primary, fallback).parse("Example JD")

    assert outcome.result.status == "valid"
    assert outcome.primary_attempts == 2
    assert len(primary_calls) == 2
    assert fallback_calls == []


def test_primary_exhaustion_uses_fallback():
    primary, primary_calls = fake_chain([{}, {}, {}])
    fallback, fallback_calls = fake_chain([valid_result()])

    outcome = JDParsingService(primary, fallback).parse("Example JD")

    assert outcome.result.status == "valid"
    assert outcome.primary_attempts == 3
    assert outcome.fallback_attempts == 1
    assert not outcome.exhausted
    assert len(primary_calls) == 3
    assert len(fallback_calls) == 1


def test_both_pipelines_exhaust_safely():
    primary, primary_calls = fake_chain([{}, {}, {}])
    fallback, fallback_calls = fake_chain([{}, {}])

    outcome = JDParsingService(primary, fallback).parse("Example JD")

    assert outcome.result.status == "needs_correction"
    assert outcome.result.requirements is None
    assert outcome.primary_attempts == 3
    assert outcome.fallback_attempts == 2
    assert outcome.exhausted
    assert len(primary_calls) == 3
    assert len(fallback_calls) == 2


def test_blank_input_makes_no_model_calls():
    primary, primary_calls = fake_chain([])
    fallback, fallback_calls = fake_chain([])

    outcome = JDParsingService(primary, fallback).parse("   ")

    assert outcome.result.status == "needs_correction"
    assert outcome.primary_attempts == 0
    assert outcome.fallback_attempts == 0
    assert not outcome.exhausted
    assert primary_calls == []
    assert fallback_calls == []


def test_oversized_input_makes_no_model_calls():
    primary, primary_calls = fake_chain([])
    fallback, fallback_calls = fake_chain([])

    outcome = JDParsingService(primary, fallback).parse("x" * 30_001)

    assert outcome.result.status == "needs_correction"
    assert outcome.primary_attempts == 0
    assert outcome.fallback_attempts == 0
    assert primary_calls == []
    assert fallback_calls == []


def test_connection_failures_exhaust_both_pipelines():
    calls = []

    def fail_connection(inputs):
        calls.append(inputs)
        raise APIConnectionError(
            request=httpx.Request(
                "POST",
                "https://api.groq.com/openai/v1/chat/completions",
            ),
        )

    failing_chain = RunnableLambda(fail_connection)
    service = JDParsingService(failing_chain, failing_chain)

    outcome = service.parse("Example JD")

    assert outcome.exhausted
    assert outcome.primary_attempts == 3
    assert outcome.fallback_attempts == 2
    assert len(calls) == 5


def test_authentication_failure_stops_without_fallback():
    calls = []

    def fail_authentication(inputs):
        calls.append(inputs)
        response = httpx.Response(
            401,
            request=httpx.Request("POST", "https://api.groq.com"),
        )
        raise AuthenticationError(
            "Invalid API key.",
            response=response,
            body=None,
        )

    primary = RunnableLambda(fail_authentication)
    fallback, fallback_calls = fake_chain([])
    service = JDParsingService(primary, fallback)

    with pytest.raises(JDParsingError, match="provider rejected"):
        service.parse("Example JD")

    assert len(calls) == 1
    assert fallback_calls == []


def test_rate_limit_stops_without_fallback():
    calls = []

    def fail_rate_limit(inputs):
        calls.append(inputs)
        response = httpx.Response(
            429,
            request=httpx.Request("POST", "https://api.groq.com"),
        )
        raise RateLimitError(
            "Rate limit reached.",
            response=response,
            body=None,
        )

    primary = RunnableLambda(fail_rate_limit)
    fallback, fallback_calls = fake_chain([])
    service = JDParsingService(primary, fallback)

    with pytest.raises(JDParsingError, match="rate-limited"):
        service.parse("Example JD")

    assert len(calls) == 1
    assert fallback_calls == []
