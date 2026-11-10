"""langchain-tavily with bounded transport and no implicit HTTP retries."""

from typing import Any
from urllib.parse import urlparse

import requests
from langchain_core.tools import ToolException
from langchain_tavily import TavilySearch
from langchain_tavily._utilities import TavilySearchAPIWrapper
from pydantic import Field, ValidationError
from requests.adapters import HTTPAdapter

from ai_interview_coach.config import Settings
from ai_interview_coach.models.job import Seniority
from ai_interview_coach.models.research import SearchOutcome, SearchSnippet


class BoundedTavilyAPIWrapper(TavilySearchAPIWrapper):
    """Version-tested extension: the installed sync wrapper omits a timeout."""

    request_timeout: float = Field(default=30, gt=0)

    def raw_results(self, **kwargs: Any) -> dict[str, Any]:
        payload = {key: value for key, value in kwargs.items() if value is not None}
        with requests.Session() as transport:
            transport.mount("https://", HTTPAdapter(max_retries=0))
            response = transport.post(
                "https://api.tavily.com/search",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.tavily_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                    "X-Client-Source": "langchain-tavily",
                },
                timeout=self.request_timeout,
                allow_redirects=False,
            )
            if response.status_code != 200:
                raise requests.HTTPError("Search provider rejected the request.", response=response)
            return response.json()


def build_search_query(skill: str, seniority: Seniority) -> str:
    return f"{seniority.value} {skill} interview questions"


class TavilyQuestionSearch:
    def __init__(self, settings: Settings) -> None:
        self.domains = settings.search_domains
        self.tool = TavilySearch(
            api_wrapper=BoundedTavilyAPIWrapper(
                tavily_api_key=settings.tavily_api_key,
                request_timeout=settings.request_timeout_seconds,
            ),
            max_results=8,
            search_depth="advanced",
            include_domains=self.domains or None,
            include_answer=False,
            include_raw_content=False,
            include_images=False,
            auto_parameters=False,
            handle_tool_error=False,
        )

    def __call__(self, skill: str, seniority: Seniority) -> SearchOutcome:
        try:
            raw = self.tool.invoke({"query": build_search_query(skill, seniority)})
        except ToolException:
            # Installed integration raises this for an empty result set.
            return SearchOutcome(status="empty")
        except (requests.RequestException, ValueError) as error:
            return classify_search_error(error)
        if not isinstance(raw, dict):
            return SearchOutcome(status="error", error_category="invalid_response")
        if "error" in raw:
            return classify_search_error(raw["error"])
        results = raw.get("results")
        if not isinstance(results, list):
            return SearchOutcome(status="error", error_category="invalid_response")
        snippets = []
        for item in results[:8]:
            if not isinstance(item, dict):
                continue
            try:
                snippet = SearchSnippet(
                    title=str(item.get("title") or "Search result")[:500],
                    url=item.get("url"),
                    content=str(item.get("content") or "").strip()[:4000],
                )
            except ValidationError:
                continue
            host = urlparse(str(snippet.url)).hostname or ""
            if self.domains and not any(
                host == domain or host.endswith("." + domain) for domain in self.domains
            ):
                continue
            snippets.append(snippet)
        return SearchOutcome(status="success" if snippets else "empty", snippets=snippets)


def classify_search_error(error: object) -> SearchOutcome:
    """Keep only a known category/status; never retain exception strings or bodies."""
    if isinstance(error, requests.HTTPError):
        response = error.response
        status = response.status_code if response is not None else None
        return SearchOutcome(status="error", error_category="http_error", http_status=status)
    if isinstance(error, requests.Timeout):
        return SearchOutcome(status="error", error_category="timeout")
    if isinstance(error, requests.ConnectionError):
        return SearchOutcome(status="error", error_category="connection_error")
    if isinstance(error, ValueError):
        return SearchOutcome(status="error", error_category="invalid_response")
    return SearchOutcome(status="error", error_category="search_error")
