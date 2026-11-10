# AI Interview Coach

A JD-focused preparation coach built incrementally with LangChain LCEL, Groq,
Tavily, Pydantic v2, and Streamlit. This repository currently contains the project
completed Milestone 1 foundation, not a working interview system.

## Setup

Install uv, then run from the project root:

```bash
uv sync --locked
cp .env.example .env
uv run streamlit run app.py
```

The project uses Python 3.12. uv can install it if needed. Add your Groq and Tavily
credentials and a supported Groq model ID (`GROQ_MODEL`) only to `.env`.
The shell validates configuration but does not call providers. Restart the server
after changing settings because successful configuration is cached.

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

The suite contains 38 tests covering configuration, data contracts, and store isolation.
Commit `uv.lock` to keep installations reproducible. After intentionally changing
dependencies, run `uv lock`, followed by `uv sync --locked`.

## Structure

```text
app.py                         Streamlit entry point
src/ai_interview_coach/
    config.py                  Environment settings and validation
    models/                    Pydantic contracts and lifecycle enums
    services/                  Application workflow and turn coordination
    chains/                    LCEL parsing, planning, evaluation and reports
    tools/                     Authorized Tavily research tool
    stores/                    Separate session, history and lineage stores
    ui/                        Streamlit rendering and user interaction
    utils/                     Bounded retries and safe activity logging
tests/
    unit/                      Isolated rules and contract tests
    integration/               Workflows with mocked provider boundaries
docs/
    architecture.md            Boundaries and design decisions
```

Configuration, job and scoring contracts, lifecycle states, separate session/history
stores, and the UI shell are implemented. Chains, tools, and services are extension
points for later milestones.
Use absolute imports from `ai_interview_coach`; the installed src layout avoids
manual `sys.path` changes.

## Learning workflow

Implement one small step at a time, understand its purpose, and verify it before
moving on. Milestone 1 is complete. Next: JD parsing and guardrails.

## Limitations

State is held in memory per Streamlit browser session and is lost on server restart
or browser-session loss. No provider integration or interview workflow exists yet.
`langchain-core` is constrained to `>=1.4,<1.6.4` to preserve the blueprint
history API before its deprecation; the lockfile records compatible dependencies.
Never commit `.env` or real credentials.
