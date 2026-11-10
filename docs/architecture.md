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

A Groq model will be selected and checked for tool calling and structured output
when the provider integration is implemented.

## Scope of this scaffold

This is a single-process local application foundation. In-memory stores and
application contracts will be implemented next; production persistence and
authentication are outside the current project scope.
