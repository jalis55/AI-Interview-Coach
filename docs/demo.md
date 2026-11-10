# Reproducible demo and release checks

## Offline demo

```bash
uv sync --locked
uv run streamlit run demo.py
```

This entry point supplies placeholder environment credentials only to its own
process and does not edit `.env`. It preloads a synthetic Python/SQL role. Both
providers are disabled for demo actions. All demo feedback is explicitly simulated,
uses defaulted score 5, and produces readiness unavailable.

Demo walkthrough:

1. Inspect the preloaded plan and click Start interview.
2. Answer all three questions. Observe stable questions across reruns.
3. Inspect the report, default-score caveat, and per-skill evidence.
4. Start 3/5/10-question focused practice on a selected skill.
5. Start a fresh interview on the same JD. Previously displayed questions remain
   excluded, while the score/history ledger resets.

`tests/integration/test_offline_demo.py` executes the shipped entry point with
provider methods blocked and verifies interview completion and practice startup.
`test_complete_ui.py` covers report, practice completion, and fresh retry using
injected providers. These tests are the reproducible demo checks, not a claim of
live-provider scoring quality.

## Live setup

```bash
cp .env.example .env
# Fill GROQ_API_KEY, TAVILY_API_KEY, and GROQ_MODEL locally.
uv run streamlit run app.py
```

Use a Groq model supporting tool calling and structured outputs. The configured
model is environment controlled. Stop and restart Streamlit after changing settings
or model classes. A full browser refresh/server restart loses ephemeral sessions.

Suggested live walkthrough: synthetic JD -> confirm -> plan -> prepare -> answer
all questions -> report -> focused practice -> fresh retry. Monitor Session activity
and Usage. In particular, check that extraction repairs never repeat search.

If a provider fails, inspect its HTTP status/category in safe activity events.
Credential, permission, account quota, and network issues require the corresponding
external correction; successful generic fallback does not establish provider health.
Do not paste keys or raw provider payloads into public issues.

## Local release checks

```bash
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

The GitHub Actions workflow repeats locked installation, lint, formatting, and tests
without repository API secrets. Dependencies are pinned by uv.lock. The application
uses Python 3.12 and makes no RAG/vector/LangGraph orchestration calls.

Before a portfolio recording, restart the server, use a synthetic JD and answers,
keep `.env` off screen, and show the actual evidence caveats. Production auth,
restart recovery, distributed locking, durable storage, account-level quotas, and
formal quality calibration are outside this local portfolio release.
