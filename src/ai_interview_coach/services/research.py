"""Bounded tool calling, one-shot research, extraction, and safe question fallback."""

import json
from collections import Counter
from collections.abc import Callable
from typing import Literal

from groq import APIConnectionError, APIStatusError, InternalServerError
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel, ConfigDict, Field

from ai_interview_coach.chains.research import (
    TOOL_NAME,
    build_question_chain,
    build_research_tool_planner,
)
from ai_interview_coach.config import Settings
from ai_interview_coach.models.job import Seniority
from ai_interview_coach.models.question import InterviewQuestion, QuestionBatch
from ai_interview_coach.models.research import QuestionResearchRequest, SearchOutcome
from ai_interview_coach.models.session import InterviewSession, InterviewStatus
from ai_interview_coach.planning.validation import validate_plan_for_requirements
from ai_interview_coach.prompts.research import TOOL_SYSTEM
from ai_interview_coach.providers.tavily import TavilyQuestionSearch, build_search_query
from ai_interview_coach.tools.generic_questions import generic_question_texts
from ai_interview_coach.tools.question_filter import filter_questions, is_duplicate
from ai_interview_coach.tools.research_policy import authorize_research_request
from ai_interview_coach.tools.research_search import search_once
from ai_interview_coach.utils.activity import emit
from ai_interview_coach.utils.reliability import run_bounded_attempts
from ai_interview_coach.utils.usage import model_config

RECOVERABLE = (APIConnectionError, InternalServerError, OutputParserException, ValueError)


class ResearchPreparationError(RuntimeError):
    """Preparation can be resumed using the existing search cache."""


class ResearchToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    name: Literal["find_interview_questions"]
    args: QuestionResearchRequest


class ResearchService:
    def __init__(
        self,
        *,
        settings: Settings,
        search: Callable[[str, Seniority], SearchOutcome],
        tool_planner: Runnable,
        extractor: Runnable,
        extractor_fallback: Runnable,
        generator: Runnable,
        generator_fallback: Runnable,
    ) -> None:
        self.settings = settings
        self.search = search
        self.tool_planner = tool_planner
        self.extractor = extractor
        self.extractor_fallback = extractor_fallback
        self.generator = generator
        self.generator_fallback = generator_fallback

    def _batch(self, session, skill, values, *, extract):
        primary = self.extractor if extract else self.generator
        fallback = self.extractor_fallback if extract else self.generator_fallback
        source = "extraction" if extract else "generation"
        for chain, limit, phase in (
            (primary, self.settings.primary_max_attempts, "primary"),
            (fallback, self.settings.fallback_max_attempts, "fallback"),
        ):
            attempt = 0

            def operation(chain=chain, phase=phase):
                nonlocal attempt
                attempt += 1
                emit(session, f"{phase}_attempt", skill=skill, attempt=attempt, source=source)
                if attempt > 1:
                    emit(session, "retry", skill=skill, attempt=attempt, source=source)
                return QuestionBatch.model_validate(
                    chain.invoke(values, config=model_config(session, source))
                )

            if phase == "fallback":
                emit(session, "fallback_started", skill=skill, source=source)
            try:
                result = run_bounded_attempts(operation, max_attempts=limit, retry_on=RECOVERABLE)
            except APIStatusError as error:
                emit(
                    session,
                    "provider_unavailable",
                    skill=skill,
                    source=source,
                    status="error",
                    **groq_diagnostics(error),
                )
                if phase == "primary" and error.status_code == 400:
                    continue
                if phase == "fallback":
                    emit(session, "fallback_finished", skill=skill, source=source, status="error")
                return QuestionBatch(questions=[])
            if phase == "fallback":
                emit(
                    session,
                    "fallback_finished",
                    skill=skill,
                    source=source,
                    status="ok" if result.succeeded else "error",
                )
            if result.succeeded:
                return result.value
        return QuestionBatch(questions=[])

    def _generic_questions(self, session, skill, difficulty, needed, exclusions):
        texts = generic_question_texts(skill)
        accepted = []
        for text in texts:
            if is_duplicate(text, exclusions + [q.question for q in accepted], skill=skill):
                continue
            accepted.append(
                InterviewQuestion(
                    question=text,
                    skill=skill,
                    difficulty=difficulty,
                    source="llm_fallback",
                    rationale=(
                        "Generic skill practice: model generation was unavailable or insufficient; "
                        "difficulty is an initial target, not a calibrated assessment."
                    ),
                )
            )
            if len(accepted) == needed:
                break
        if len(accepted) < needed:
            raise ResearchPreparationError(
                "We could not prepare enough unused questions. Existing progress is preserved."
            )
        emit(session, "safe_default", skill=skill, count=len(accepted), source="llm_fallback")
        return accepted

    def find_interview_questions(self, session: InterviewSession, skill: str) -> QuestionBatch:
        if session.requirements is None or session.plan is None:
            raise ResearchPreparationError("Confirmed requirements and a plan are required.")
        request = QuestionResearchRequest(skill=skill)
        authorize_research_request(request, requirements=session.requirements, plan=session.plan)
        return self._prepare_skill(session, request.skill, web=True)

    def _prepare_skill(self, session, skill, *, web):
        slots = [slot for slot in session.plan.slots if slot.skill == skill]
        difficulty = slots[0].target_difficulty
        needed = len(slots)
        existing = [
            q
            for q in session.candidate_pool
            if q.skill == skill
            and not is_duplicate(q.question, session.asked_questions, skill=skill)
        ]
        if sum(q.difficulty == difficulty for q in existing) >= needed:
            return QuestionBatch(questions=existing[: self.settings.candidates_per_skill])
        exclusions = session.asked_questions + [q.question for q in session.candidate_pool]
        research = SearchOutcome(status="empty")
        if web:
            # The query contains only authorized skill and seniority, never full JD/answers.
            emit(
                session,
                "search_query",
                skill=skill,
                query=build_search_query(skill, session.requirements.seniority),
            )
            research = search_once(
                session, QuestionResearchRequest(skill=skill), search=self.search
            )
        values = {
            "limit": self.settings.candidates_per_skill,
            "requirements": session.requirements.model_dump_json(),
            "jd_context": session.jd_context[:30_000],
            "skill": skill,
            "difficulty": difficulty.value,
            "snippets": research.model_dump_json(),
            "exclusions": json.dumps(exclusions[-100:]),
        }
        questions = list(existing)
        if research.status == "success":
            batch = self._batch(session, skill, values, extract=True)
            questions.extend(
                filter_questions(
                    batch,
                    skill=skill,
                    research=research,
                    exclusions=exclusions,
                    web=True,
                    limit=self.settings.candidates_per_skill,
                )
            )
        if len(questions) < self.settings.candidates_per_skill:
            values["exclusions"] = json.dumps((exclusions + [q.question for q in questions])[-100:])
            batch = self._batch(session, skill, values, extract=False)
            questions.extend(
                filter_questions(
                    batch,
                    skill=skill,
                    research=research,
                    exclusions=exclusions + [q.question for q in questions],
                    web=False,
                    limit=self.settings.candidates_per_skill - len(questions),
                )
            )
        target_count = sum(q.difficulty == difficulty for q in questions)
        if target_count < needed:
            questions.extend(
                self._generic_questions(
                    session,
                    skill,
                    difficulty,
                    needed - target_count,
                    exclusions + [q.question for q in questions],
                )
            )
        # Preserve target-level coverage before retaining optional alternate difficulties.
        questions.sort(key=lambda q: q.difficulty != difficulty)
        questions = questions[: self.settings.candidates_per_skill]
        others = [q for q in session.candidate_pool if q.skill != skill]
        if len(others) + len(questions) > self.settings.candidate_pool_limit:
            raise ResearchPreparationError(
                "The question pool limit was reached. Edit the plan to continue."
            )
        session.candidate_pool = others + questions
        for source, count in Counter(q.source.value for q in questions).items():
            emit(session, "candidates_ready", skill=skill, source=source, count=count)
        return QuestionBatch(questions=questions)

    def generate_for_turn(self, session, skill, difficulty):
        if session.requirements is None or skill not in {
            *session.requirements.core_skills,
            "behavioral",
        }:
            raise ResearchPreparationError("Question skill is outside confirmed requirements.")
        exclusions = session.asked_questions + [q.question for q in session.candidate_pool]
        research = session.search_cache.get(
            (skill, session.requirements.seniority), SearchOutcome(status="empty")
        )
        values = {
            "limit": self.settings.candidates_per_skill,
            "requirements": session.requirements.model_dump_json(),
            "jd_context": session.jd_context[:30_000],
            "skill": skill,
            "difficulty": difficulty.value,
            "snippets": research.model_dump_json(),
            "exclusions": json.dumps(exclusions[-100:]),
        }
        if session.is_demo:
            questions = []
        else:
            batch = self._batch(session, skill, values, extract=False)
            questions = [
                q
                for q in filter_questions(
                    batch,
                    skill=skill,
                    research=research,
                    exclusions=exclusions,
                    web=False,
                    limit=self.settings.candidates_per_skill,
                )
                if q.difficulty == difficulty
            ]
        if not questions:
            questions = self._generic_questions(session, skill, difficulty, 1, exclusions)
        return questions

    def _request_message(self, session, messages):
        attempt = 0

        def operation():
            nonlocal attempt
            attempt += 1
            emit(session, "primary_attempt", source="tool_planner", attempt=attempt)
            if attempt > 1:
                emit(session, "retry", source="tool_planner", attempt=attempt)
            reply = self.tool_planner.invoke(
                messages, config=model_config(session, "research_tool_planner")
            )
            if not isinstance(reply, AIMessage) or reply.invalid_tool_calls:
                raise ValueError("Invalid tool planner response.")
            if len(reply.tool_calls) > len(session.plan.prioritized_skills):
                raise ValueError("Too many tool requests.")
            ids = set()
            for call in reply.tool_calls:
                adapted = ResearchToolCall.model_validate(
                    {
                        "id": call.get("id"),
                        "name": call.get("name"),
                        "args": call.get("args"),
                    }
                )
                if adapted.id in ids:
                    raise ValueError("Repeated tool-call ID.")
                ids.add(adapted.id)
                authorize_research_request(
                    adapted.args,
                    requirements=session.requirements,
                    plan=session.plan,
                )
            return reply

        try:
            result = run_bounded_attempts(
                operation,
                max_attempts=self.settings.primary_max_attempts,
                retry_on=RECOVERABLE,
            )
        except APIStatusError as error:
            emit(
                session,
                "provider_unavailable",
                source="tool_planner",
                status="error",
                **groq_diagnostics(error),
            )
            return None
        return result.value if result.succeeded else None

    def prepare(
        self,
        session: InterviewSession,
        *,
        on_skill_ready: Callable[[str], None] | None = None,
    ) -> None:
        if session.requirements is None or session.plan is None:
            raise ResearchPreparationError("Confirm requirements and create a plan first.")
        session.plan = validate_plan_for_requirements(session.plan, session.requirements)
        if session.research_complete:
            return
        session.status = InterviewStatus.PREPARING
        allowed = set(session.plan.prioritized_skills) | {"behavioral"}
        session.candidate_pool = [q for q in session.candidate_pool if q.skill in allowed]
        messages = [
            SystemMessage(content=TOOL_SYSTEM),
            HumanMessage(
                content=json.dumps(
                    {
                        "authorized_skills": session.plan.prioritized_skills,
                    }
                )
            ),
        ]
        completed = set()
        call_ids = set()
        try:
            for _ in range(self.settings.tool_loop_max_iterations):
                reply = self._request_message(session, messages)
                if reply is None or not reply.tool_calls:
                    break
                if any(call["id"] in call_ids for call in reply.tool_calls):
                    break
                messages.append(reply)
                for call in reply.tool_calls:
                    call_ids.add(call["id"])
                    request = QuestionResearchRequest.model_validate(call["args"])
                    batch = self.find_interview_questions(session, request.skill)
                    completed.add(request.skill)
                    if on_skill_ready:
                        on_skill_ready(request.skill)
                    messages.append(
                        ToolMessage(
                            tool_call_id=call["id"],
                            name=TOOL_NAME,
                            content=json.dumps(
                                {"skill": request.skill, "candidate_count": len(batch.questions)}
                            ),
                        )
                    )
                if completed == set(session.plan.prioritized_skills):
                    break
            # Deterministic planner fallback still passes authorization and budget checks.
            for skill in session.plan.prioritized_skills:
                if skill not in completed:
                    emit(session, "tool_plan_fallback", skill=skill)
                    self.find_interview_questions(session, skill)
                    if on_skill_ready:
                        on_skill_ready(skill)
            self._prepare_skill(session, "behavioral", web=False)
            if on_skill_ready:
                on_skill_ready("behavioral")
        except Exception:
            session.status = InterviewStatus.RECOVERABLE_ERROR
            raise
        session.research_complete = True
        emit(session, "research_complete", count=len(session.candidate_pool))


def create_research_service(settings: Settings) -> ResearchService:
    return ResearchService(
        settings=settings,
        search=TavilyQuestionSearch(settings),
        tool_planner=build_research_tool_planner(),
        extractor=build_question_chain(extract=True),
        extractor_fallback=build_question_chain(extract=True, fallback=True),
        generator=build_question_chain(extract=False),
        generator_fallback=build_question_chain(extract=False, fallback=True),
    )


def groq_diagnostics(error: APIStatusError) -> dict[str, str | int]:
    """Expose only fixed provider labels, HTTP status, and allowlisted error codes."""
    details: dict[str, str | int] = {
        "provider": "groq",
        "http_status": error.status_code,
    }
    code = getattr(error, "code", None)
    body = getattr(error, "body", None)
    if code is None and isinstance(body, dict):
        details_body = body.get("error", body)
        if isinstance(details_body, dict):
            code = details_body.get("code")
    if isinstance(code, str) and code in {
        "json_validate_failed",
        "tool_use_failed",
        "rate_limit_exceeded",
        "insufficient_quota",
        "invalid_api_key",
        "model_not_found",
    }:
        details["error_code"] = code
    return details
