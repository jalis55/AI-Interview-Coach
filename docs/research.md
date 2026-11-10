# Milestone 4: controlled question research

## Read the implementation in this order

1. `models/research.py`: a skill-only request and bounded evidence outcomes.
2. `tools/research_policy.py`: require a valid plan and selected core skill.
3. `tools/research_search.py`: cache, then budget, then reserve, then invoke once.
4. `providers/tavily.py`: adapt the installed package to a timed HTTP request.
5. `tools/question_filter.py`: provenance, question shape, relevance, and exclusions.
6. `chains/research.py` and `prompts/research.py`: separate LCEL extraction and generation.
7. `services/research.py`: coordinate those pieces and the bounded tool loop.
8. `ui/research.py`: explicit preparation, source counts, and activity events.

## One skill, one search allowance

```text
validated tool request
  -> selected-skill authorization
  -> existing candidate coverage? reuse it
  -> cached search outcome? reuse it
  -> allowance spent? use cached error outcome, no new search
  -> reserve allowance and provisional error
  -> invoke Tavily once
  -> cache success / empty / error
  -> extract with bounded local retries
  -> generate validated replacements if insufficient
  -> generic labeled practice or recoverable novelty error
```

The search budget is independent of difficulty and seniority changes. Cache keys
include skill and seniority; counters use skill alone. Search evidence is generic
skill research, while candidate questions use confirmed JD context. Editing clears
candidates without resetting search allowances.

## Controlled tool calling

The bound Groq model can request only `find_interview_questions(skill=...)`.
`ResearchToolCall` validates names, IDs, and argument schemas; the application
checks skills against the confirmed plan before executing any call in a batch.
Tool results use matching `ToolMessage.tool_call_id` values. Loop iterations,
requests per response, and repair attempts are bounded. Missing/invalid planner
requests eventually use deterministic selected-skill execution through the same
policy and budget checks. Behavioral candidates use generation without search.

Each question chain has primary structured output, stricter JSON-parser fallback,
and a terminal safe outcome. The planner uses deterministic authorized requests
as its terminal fallback. Safe defaults have generic-practice rationales and
`llm_fallback` labels; they are not presented as discovered web questions.

## Provider compatibility

The installed langchain-tavily 0.2.18 sync wrapper uses `requests.post` without a
timeout. `BoundedTavilyAPIWrapper` subclasses its internal API wrapper to supply a
fixed endpoint, explicit timeout, no redirects, and `HTTPAdapter(max_retries=0)`.
This is a version-sensitive integration boundary: run `test_tavily_adapter.py`
when upgrading the package. `handle_tool_error=False` lets empty-result exceptions
reach the adapter instead of becoming plain text. No query-refinement retry exists.

## Recovery and observability

Successful skills commit candidates independently. A failed later skill does not
erase earlier progress. Retry preparation uses retained caches and allowances.
Research completeness is separate from lifecycle status: pool readiness stays in
`preparing` until Milestone 5 displays the current question. Unexpected programming
exceptions propagate; expected provider failures take safe paths. An inability to
produce unused generic questions produces `recoverable_error` rather than repeats.

Activity events are session-scoped, capped at 300 entries, and contain approved
metadata such as skill, query, counts, provenance, cache state, and attempts.
They exclude raw prompts, JD text, answers, keys, and provider error payloads.
The sidebar shows recent events; the preparation status reports each finished skill.

## Verification

Automated checks use fake provider responses: success, empty results, failed HTTP,
timeouts, malformed model output, unauthorized skills, invalid tool names/arguments,
call-ID associations, cache reuse, extraction retries, honest provenance, exclusions,
novelty failure, pool bounds, separate sessions, and Streamlit reruns/edit invalidation.
They exercise the installed Tavily tool against a fake HTTP transport.

A live smoke check is deliberately manual and costs provider usage:

1. Start Streamlit with your configured keys and a supported Groq model.
2. Analyze a synthetic JD requiring only Python, confirm, and create a plan.
3. Click Prepare questions. Inspect the activity sidebar for one Python search.
4. Confirm Python and behavioral candidate counts, honest fallback labels, and
   no extra search after a rerun. Questions are selected and shown in Milestone 5.
5. If the provider is unavailable, inspect the cached error and generic-practice
   disclosure. Do not rerun Tavily to repair extraction.

No live provider call is part of the automated tests. Lexical relevance checks and
near-text duplicate detection cannot establish semantic uniqueness or employer
provenance. Candidate review and later evaluation must retain those limitations.
