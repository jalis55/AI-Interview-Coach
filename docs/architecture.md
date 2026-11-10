# Architecture

## Dependency direction

Streamlit UI -> interview service -> chains, tools, and stores.

- UI renders data and sends user actions to the service.
- Services own workflow transitions and commit validated results.
- Chains accept explicit inputs and return validated outputs using LCEL.
- Tools enforce authorized skills, research budgets, and provenance.
- Models define Pydantic contracts shared across these boundaries.
- Stores keep session state, chat history, and retry lineage separate.
- Utilities support bounded retries and safe activity events.

## Provider choices

Groq replaces the specification's OpenAI default, as requested by the user.
Use `langchain-groq` for models, `langchain-tavily` for search, and
`langchain-core` for LCEL primitives. No RAG, LangGraph, or vector store is needed.
The installed Tavily integration transitively brings in `langchain` and `langgraph`;
application code will not use LangGraph. Keep normal dependency resolution intact
rather than removing transitive packages manually.

The configured Groq model is used for structured parsing and validated tool requests.
See research.md for the version-sensitive Tavily transport boundary and failure policy.

## Current scope

This is a single-process local application with isolated in-memory state, JD review,
validated coverage planning, controlled question research, an idempotent interview
loop, scoring, adaptive practice, evidence reporting, retry lineage, and usage callbacks.
Production persistence and authentication remain outside the current project scope.

See interview.md for turn staging/commit boundaries, the scoped legacy LCEL history
compatibility notice, report arithmetic, and fresh-retry versus practice semantics.
