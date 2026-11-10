"""Exercise the installed langchain-tavily integration with fake HTTP transport."""

from types import SimpleNamespace

import pytest
import requests

from ai_interview_coach.config import Settings
from ai_interview_coach.models.job import Seniority
from ai_interview_coach.providers.tavily import TavilyQuestionSearch


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        groq_api_key="fake-groq",
        tavily_api_key="fake-tavily",
        groq_model="test-model",
        search_domains=["example.com"],
        request_timeout_seconds=12,
    )


def install_transport(monkeypatch, payload, *, status=200, failure=None):
    calls = []
    adapters = []

    class Transport:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def mount(self, scheme, adapter):
            adapters.append(adapter)

        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            if failure:
                raise failure
            return SimpleNamespace(status_code=status, json=lambda: payload)

    monkeypatch.setattr(requests, "Session", Transport)
    return calls, adapters


def test_transport_uses_timeout_fixed_options_and_no_retries(monkeypatch, settings):
    calls, adapters = install_transport(
        monkeypatch,
        {
            "results": [
                {
                    "title": "Python",
                    "url": "https://example.com/python",
                    "content": "x" * 5000,
                }
            ]
        },
    )
    outcome = TavilyQuestionSearch(settings)("python", Seniority.MID)
    assert outcome.status == "success"
    assert len(outcome.snippets[0].content) == 4000
    assert len(calls) == 1
    url, options = calls[0]
    assert url == "https://api.tavily.com/search"
    assert options["timeout"] == 12
    assert options["allow_redirects"] is False
    assert options["json"]["max_results"] == 8
    assert options["json"]["search_depth"] == "advanced"
    assert options["json"]["include_domains"] == ["example.com"]
    assert options["json"]["query"] == "mid python interview questions"
    assert adapters[0].max_retries.total == 0


@pytest.mark.parametrize("failure", [requests.Timeout(), requests.ConnectionError()])
def test_transport_failure_is_error_without_retry(monkeypatch, settings, failure):
    calls, _ = install_transport(monkeypatch, {}, failure=failure)
    assert TavilyQuestionSearch(settings)("python", Seniority.MID).status == "error"
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [{"results": []}, {"results": [None, {}]}])
def test_empty_or_unusable_results_are_empty(monkeypatch, settings, payload):
    calls, _ = install_transport(monkeypatch, payload)
    assert TavilyQuestionSearch(settings)("python", Seniority.MID).status == "empty"
    assert len(calls) == 1


def test_http_error_is_not_retried(monkeypatch, settings):
    calls, _ = install_transport(monkeypatch, {}, status=429)
    assert TavilyQuestionSearch(settings)("python", Seniority.MID).status == "error"
    assert len(calls) == 1


def test_filters_unallowed_domains_and_caps_results(monkeypatch, settings):
    results = [{"title": "Python", "url": "https://evil-example.com", "content": "Python?"}]
    results += [
        {
            "title": "Python",
            "url": f"https://docs.example.com/{i}",
            "content": "Python questions",
        }
        for i in range(10)
    ]
    install_transport(monkeypatch, {"results": results})
    outcome = TavilyQuestionSearch(settings)("python", Seniority.MID)
    assert len(outcome.snippets) == 7
    assert all("docs.example.com" in str(s.url) for s in outcome.snippets)


@pytest.mark.parametrize("http_status", [400, 401, 403, 429, 500])
def test_http_failure_retains_only_safe_status(monkeypatch, settings, http_status):
    install_transport(monkeypatch, {"error": "DO_NOT_LOG_SECRET"}, status=http_status)
    outcome = TavilyQuestionSearch(settings)("python", Seniority.MID)
    assert outcome.http_status == http_status
    assert outcome.error_category == "http_error"
    assert "DO_NOT_LOG_SECRET" not in outcome.model_dump_json()
