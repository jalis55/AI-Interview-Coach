"""Conservative provenance, relevance, and best-effort novelty checks."""

import re
from difflib import SequenceMatcher
from uuid import uuid4

from ai_interview_coach.models.question import InterviewQuestion, QuestionBatch
from ai_interview_coach.models.research import SearchOutcome


def normalize_text(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9+#]+", text.casefold()))


def is_duplicate(text: str, exclusions: list[str], *, skill: str | None = None) -> bool:
    normalized = normalize_text(text)
    return any(
        normalized == normalize_text(other)
        or (
            (skill is None or f" {normalize_text(skill)} " in f" {normalize_text(other)} ")
            and SequenceMatcher(None, normalized, normalize_text(other)).ratio() >= 0.9
        )
        for other in exclusions
    )


def looks_like_question(text: str) -> bool:
    clean = text.strip()
    return 20 <= len(clean) <= 1500 and (
        clean.endswith("?")
        or clean.casefold().startswith(
            ("explain ", "describe ", "compare ", "design ", "implement ")
        )
    )


def is_relevant(text: str, skill: str) -> bool:
    # Conservative lexical check; semantic relevance also belongs to the extractor prompt.
    aliases = {
        "python": {"python", "gil", "decorator", "generator", "iterator", "comprehension"},
        "sql": {"sql", "query", "queries", "database", "join", "index", "transaction"},
        "behavioral": {"situation", "experience", "team", "conflict", "decision", "project"},
    }
    terms = set(normalize_text(skill).split()) | aliases.get(skill, set())
    return bool(terms & set(normalize_text(text).split()))


def filter_questions(
    batch: QuestionBatch,
    *,
    skill: str,
    research: SearchOutcome,
    exclusions: list[str],
    web: bool,
    limit: int,
) -> list[InterviewQuestion]:
    accepted = []
    seen = list(exclusions)
    snippets = {str(item.url): item for item in research.snippets}
    for question in batch.questions:
        if question.skill != skill or not looks_like_question(question.question):
            continue
        if not is_relevant(question.question, skill) or is_duplicate(
            question.question, seen, skill=skill
        ):
            continue
        data = question.model_dump()
        if web:
            evidence = snippets.get(str(question.source_url))
            if question.source != "web" or evidence is None:
                continue
            # Only verbatim extraction earns web provenance, never a rewritten question.
            if normalize_text(question.question) not in normalize_text(evidence.content):
                continue
            data.update(source="web", source_url=evidence.url, source_title=evidence.title)
        else:
            data.update(source="llm_fallback", source_url=None, source_title=None)
        data["id"] = uuid4()
        candidate = InterviewQuestion.model_validate(data)
        accepted.append(candidate)
        seen.append(candidate.question)
        if len(accepted) >= limit:
            break
    return accepted
