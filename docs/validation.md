# Validation record

Validation date: 10 November 2026 (Asia/Dhaka).

## Automated checks

- 198 passing tests, including isolated contracts, mocked HTTP/provider failures,
  complete interview/practice/retry flows, concurrent submit protection, and Streamlit UI.
- The suite also passes from an empty working directory with Groq/Tavily environment
  credentials unset, verifying that tests do not rely on the local .env.
- Ruff lint and formatting pass.
- Locked uv synchronization succeeds offline against the installed environment.
- Source distribution and wheel build successfully.
- The shipped offline demo completes its interview/report and starts practice with
  Groq and Tavily methods explicitly blocked in the integration test.

## Live compatibility check

A synthetic Python question and answer were sent in one Groq request. The configured
`openai/gpt-oss-120b` model returned a valid accepted evaluation with integer score 8.
The usage callback recorded one metered call, 653 input tokens and 395 output tokens.
This verifies request/schema compatibility and token accounting for that response,
not the calibration or general quality of the coaching rubric.

One Tavily search for `mid python interview questions` returned HTTP 401 with zero
snippets. The transport and safe error classification worked, but the configured
credentials were rejected. The local API key is deliberately not copied into source,
logs, docs, or Git. Live web research requires accepted Tavily credentials and a new
session/search budget; no repeated search was performed to repair this failure.

A complete live-provider interview was not claimed. End-to-end lifecycle/recovery
is verified with injected provider responses and the offline demo. Correcting the
Tavily credentials and running the live walkthrough in demo.md remains the external
integration follow-up.

## Tested dependency versions

See uv.lock for the full reproducible dependency graph. Runtime versions were
recorded from the actual installed environment during release preparation.

| Package | Tested version |
|---|---|
| langchain-core | 1.6.3 |
| langchain-groq | 1.1.3 |
| langchain-tavily | 0.2.18 |
| pydantic | 2.14.3 |
| pydantic-settings | 2.16.2 |
| streamlit | 1.67.0 |
| pytest | 9.2.0 |
| ruff | 0.17.4 |
