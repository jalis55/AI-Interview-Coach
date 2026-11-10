# AI Interview Coach

A JD-focused preparation coach built incrementally with LangChain LCEL, Groq,
Tavily, Pydantic v2, and Streamlit. Milestones 1-4 implement requirements review,
coverage planning, and question preparation. The interview loop comes next.

## Setup

Install uv, then run from the project root:

```bash
uv sync --locked
cp .env.example .env
uv run streamlit run app.py
```

Use Python 3.12. Add `GROQ_API_KEY`, `TAVILY_API_KEY`, and a supported
`GROQ_MODEL` to `.env`. Never commit real credentials. Restart Streamlit after
changing settings or model classes because settings and session objects are cached.

## Current workflow

1. Paste a JD and analyze it with Groq.
2. Review and edit the extraction, then confirm it. Missing seniority defaults to
   mid for preparation; the review message discloses that assumption.
3. Create a coverage plan. Question count is `min(10, max(3, core_skill_count + 1))`.
   Exactly one slot is behavioral. A validated plan changes status to `ready`.
4. Click **Prepare questions**. The application validates model tool requests,
   researches selected technical skills, and builds a source-aware candidate pool.
5. Inspect coverage counts and research activity. Status remains `preparing` after
   the pool is ready; Milestone 5 will display the first question and transition
   to `awaiting_answer`.

Analyzing, planning, and preparing make provider calls. Editing and confirmation do
not. Prepared results survive widget reruns without automatic repeated paid calls.

## Research guarantees and limits

- At most one Tavily invocation per normalized skill per session, including failures.
  The budget is reserved before invocation. Empty and error outcomes are cached.
- Queries contain only authorized skill and seniority. Original JDs and answers are
  not sent to Tavily. Groq receives JD context for extraction/generation.
- Tavily uses advanced depth, at most eight results, configurable domain filters,
  explicit timeouts, no redirects, and no automatic HTTP retries.
- Extraction retries use bounded cached snippets, never a second search.
- Structured-output chains have bounded attempts (up to three primary and two JSON
  fallback attempts). Terminal behavior generates clearly labeled generic practice
  questions or returns a recoverable error if novelty cannot be maintained.
- Web labels require a returned source URL and question wording present in the
  bounded evidence snippet. Newly generated questions use `llm_fallback`.
- Relevance filtering is conservative and partly lexical; question quality and
  paraphrase detection are best-effort. Sources are not verified employer questions.
- Research runs sequentially. The in-memory budget is not a multi-worker lock.
- Editing requirements clears JD-sensitive candidates and the plan but retains
  research budgets and cache within the same session. A seniority change does not
  grant another search allowance for an already researched skill.

Optional `.env` configuration uses JSON for lists:

```dotenv
SEARCH_DOMAINS=["geeksforgeeks.org","interviewbit.com","stackoverflow.com"]
CANDIDATES_PER_SKILL=6
CANDIDATE_POOL_LIMIT=90
TOOL_LOOP_MAX_ITERATIONS=3
```

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

The tests mock paid providers, including real langchain-tavily transport boundaries,
so the suite needs no real API keys. Commit `uv.lock` for reproducible installs.
After intentionally changing dependencies, run `uv lock` and `uv sync --locked`.
See [research design](docs/research.md) for the module map and a manual integration check.

## Structure

```text
app.py                         Streamlit entry point
src/ai_interview_coach/
    config.py                  Validated environment settings
    models/                    Data contracts and lifecycle enums
    prompts/                   Instructions separate from orchestration
    chains/                    LCEL parsing, planning, extraction and generation
    providers/                 Groq factory and bounded Tavily adapter
    planning/                  Deterministic allocation and validation
    services/                  Application workflow and controlled tool execution
    tools/                     Research authorization, budgets and question filtering
    stores/                    Separate session and conversation-history stores
    ui/                        Streamlit rendering and explicit actions
    utils/                     Bounded attempts and safe activity events
tests/unit/                   Contract, failure-path and mocked UI tests
docs/                         Architecture and research notes
```

## Limitations

State is in memory per Streamlit browser session and is lost on server restart or
browser-session loss. Authentication, persistent accounts, scoring, reporting,
retry lineage, and usage accounting are future work. No interview price is quoted:
LLM/search costs must be measured against current provider billing.
`langchain-core` is constrained to `>=1.4,<1.6.4` to preserve the blueprint history
API before its deprecation; the lockfile records compatible dependencies.
Application code uses no RAG, LangGraph, or vector store. LangGraph is a transitive
package dependency, not the application's orchestration mechanism.
