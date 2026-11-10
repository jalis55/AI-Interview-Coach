# AI Interview Coach

A job-description-focused preparation coach built with LangChain LCEL, Groq, Tavily,
Pydantic v2, Streamlit, and uv. The ten implementation milestones now cover JD review,
coverage planning, controlled research, interviewing, scoring, adaptive practice,
evidence reports, fresh retries, and usage accounting.

## Run locally

Install uv and run from the project root:

```bash
uv sync --locked
cp .env.example .env
# Fill GROQ_API_KEY, TAVILY_API_KEY, and GROQ_MODEL locally.
uv run streamlit run app.py
```

Python 3.12 is required. Select a Groq model supporting tool calling and structured
output; `openai/gpt-oss-120b` was used for the live evaluation smoke check. Never
commit real credentials. Restart Streamlit after changing configuration or model
classes. Sessions are ephemeral and disappear on server/browser-session loss.

## Offline demo

No provider account is needed for the reproducible demo:

```bash
uv run streamlit run demo.py
```

It loads a synthetic Python/SQL role and uses no provider calls. Demo feedback is
explicitly simulated, recorded as neutral/defaulted 5, and never claims readiness.
See [demo walkthrough](docs/demo.md).

## User journey

1. Paste a JD and analyze it. Review/edit the extracted role, level, and core skills.
   Missing seniority defaults to mid for preparation and is disclosed during review.
2. Confirm requirements and create a coverage plan. Initial question count is
   `min(10, max(3, core_skill_count + 1))`, including exactly one behavioral slot.
   One skill gets two technical slots; more than nine skills explicitly omits some.
3. Prepare questions. Each selected technical skill has at most one Tavily invocation
   per session, including failures. Empty/error results are cached too.
4. Start the interview, answer one question at a time, and receive score/feedback.
   Stable turn IDs and an application ledger prevent double scoring on reruns.
5. Read the report with observed difficulty, reliable evidence, insufficiently assessed
   skills, target-level gaps, omitted skills, and defaulted-score caveats.
6. Choose 3, 5, or 10 additional questions on suggested gaps. Practice retains the fixed
   JD target, research cache, search allowance, evidence, and asked-question exclusions.
7. Start a fresh interview on the same JD for new scores/history/search budget, while
   retaining prior displayed-question exclusions. A new JD starts an unrelated lineage.

Analyzing, planning, research, scoring, and report summaries can make Groq calls.
Only research invokes Tavily. Editing, confirming, display reruns, and cached reports
make no automatic repeated provider calls. Just-in-time replacement generation and
focused practice never expand the existing search budget.

## Reliability and honest assessment

- Structured outputs are validated with Pydantic. Model chains use bounded primary
  attempts and fallback policies; evaluation allows up to three primary and two JSON
  fallback attempts. Groq SDK retries are disabled.
- Valid scores below 4 lower only that skill's practice difficulty; above 8 raise it.
  Scores 4-8 keep it unchanged. Levels clamp to easy/medium/hard; JD targets stay fixed.
- Failed evaluation records a neutral 5 with an apology and `defaulted` status. It
  never adapts difficulty or supports ability claims. All-default reports show
  readiness unavailable.
- The recorded average includes every stored score, including fallback 5 values.
  Reliable per-skill averages exclude defaults. Scores across difficulties are not
  calibrated hiring predictions, and one question cannot establish mastery.
- Report branches run with `RunnableParallel`; branch failure preserves deterministic
  arithmetic and evidence-based fallback text. Later practice reports are cumulative.
- Search uses advanced depth, max eight results, explicit timeouts, configured domains,
  no redirects, and no automatic HTTP retries. Extraction retries only cached snippets.
- Web provenance requires a returned URL and question wording supported by its snippet.
  Generated/rewritten questions use `llm_fallback`. Generic last-resort prompts are
  clearly disclosed. No source is represented as a verified employer question.
- Relevance and paraphrase exclusion remain best-effort. If no unused question can
  be prepared, progress is preserved and a recoverable error appears instead of repeats.

## Usage and privacy

The sidebar shows stage activity, attempted/failed LLM calls, reported input/output
tokens, retries, fallback paths, safe defaults, and consumed search allowances.
Unreported tokens and dollar cost are not guessed. Check current provider billing
before quoting an interview price.

Groq receives JD/answer context for coaching. Tavily receives only authorized skill
and seniority, not the full JD or candidate answers. Answers are intentionally held
in isolated in-memory records/history for the report; routine activity events exclude
raw prompts, JD text, answers, keys, and provider error payloads. Downloaded reports
are user-controlled exports. Production persistence and authentication are not included.

## Verification

```bash
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv build
```

The automated suite uses fake provider boundaries and requires no real API keys.
It includes complete Streamlit, failure-path, concurrency, practice, and retry tests.
GitHub Actions repeats locked installation, lint, format, and tests without API secrets.
See [validation results](docs/validation.md) for tested versions and live-check limits.

## Configuration

Defaults are in `config.py`. Optional `.env` entries include:

```dotenv
SEARCH_DOMAINS=["geeksforgeeks.org","interviewbit.com","stackoverflow.com"]
CANDIDATES_PER_SKILL=6
CANDIDATE_POOL_LIMIT=90
TOOL_LOOP_MAX_ITERATIONS=3
REQUEST_TIMEOUT_SECONDS=30
PRIMARY_MAX_ATTEMPTS=3
FALLBACK_MAX_ATTEMPTS=2
HISTORY_MAX_MESSAGES=18
HISTORY_MAX_CHARACTERS=24000
MAX_ANSWER_CHARACTERS=12000
MAX_OUTPUT_TOKENS=4096
```

## Structure and learning notes

```text
app.py / demo.py               Live and offline Streamlit entry points
src/ai_interview_coach/
    models/                    Contracts, progress ledger, reports, usage
    prompts/                   Instructions separate from orchestration
    chains/                    LCEL pipelines, history adapter, difficulty branch
    providers/                 Groq factory and bounded Tavily transport
    planning/                  Deterministic allocation and plan validation
    services/                  Workflow, evaluation, reporting, research, retry
    stores/                    Separate session, message-history, and lineage stores
    tools/                     Authorization, budgets, provenance and novelty checks
    ui/                        Rendering and explicit user actions
    utils/                     Bounded attempts, activity events, usage callbacks
tests/unit/                    Contracts and isolated failure behavior
tests/integration/             Full lifecycle, concurrency, offline and UI checks
docs/                          Architecture, research, interview and release notes
```

Read [architecture](docs/architecture.md), [research](docs/research.md),
[interview services](docs/interview.md), and [milestone/concept coverage](docs/concept_coverage.md).

The application uses no RAG, vector store, legacy Chain subclass, or LangGraph
orchestration. LangGraph exists only as a transitive integration dependency. The
locked LCEL history API has a narrowly documented compatibility warning adapter;
see architecture notes before upgrading dependencies. In-memory single-process
locking is not distributed persistence or production access control.
