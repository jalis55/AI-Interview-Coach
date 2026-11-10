# Interview implementation: Milestones 5-10

## Lifecycle and ownership

The application owns workflow state. Models never choose progress counters, mutate
stores, expand search budgets, or change the confirmed JD target level.

```text
DRAFT -> READY -> PREPARING -> AWAITING_ANSWER -> EVALUATING
                                  ^                  |
                                  +-- next question -+
                                                     |
                                                     v
                                                COMPLETED
                                                     |
                                      optional focused practice
```

Expected recoverable failures preserve the turn/ledger and expose a retry action.
Preparation may have finished while status is `preparing`; `Start interview` displays
the first question and transitions to `awaiting_answer`.

## Read the code in this order

1. `models/interview.py`: decisions, evaluation records, and the turn ledger.
2. `chains/adaptation.py`: threshold rules using `RunnableBranch`.
3. `services/validated_call.py`: 3 primary + 2 fallback attempt bounds.
4. `chains/evaluator.py`: structured/JSON output and staged message history.
5. `services/evaluation.py`: validated evaluation or explicitly defaulted neutral 5.
6. `services/interview.py`: display, submit, atomic ledger replacement, and practice.
7. `services/reporting.py`: `RunnableParallel`, exact mean, and evidence summaries.
8. `stores/lineage_store.py`: displayed-question exclusions across fresh retries.
9. `utils/usage.py`: callback-based request and token accounting.
10. `ui/interview.py`: presentation of questions, feedback, report, practice, and retry.

## Idempotent turns

Displaying a question assigns a stable turn ID and immediately records its text in
both session and lineage exclusions. Reruns reuse the current question and ID.
Per-session locks serialize display/round changes and prevent concurrent evaluation. Duplicate submissions with the
same turn ID and answer return the saved record; a changed answer for an already
processed turn is rejected.

An accepted evaluation is stored as a pending result before the ledger commit.
The service builds a complete updated `InterviewProgress`, validates its snapshot,
and replaces the ledger once. If a later commit step fails, the pending result is
reused without another evaluation call. Scores, processed IDs, index, and practice
levels are committed together. Report generation happens after the turn commit;
retrying a report does not score the answer again.

This is process-local coordination, not a distributed transaction. A process crash
loses in-memory state. A provider may have accepted a request even if a transport
failure prevents its response from reaching the application; bounded transport
retries can therefore still incur usage on a failed logical attempt.

## History boundary

`RunnableWithMessageHistory` wraps the evaluation runnable and receives the
application's `session_id`. Each evaluation uses staged history copied from the
separate history store. Failed parser attempts and unrelated requests do not
modify committed conversation history. After a validated record commits, history
is synchronized from the application ledger and bounded to recent messages. Model-facing history also has a total character limit.
Application records retain full evidence for reports; prompts use bounded context.

The locked LCEL version warns that `RunnableWithMessageHistory` is deprecated in
favor of LangGraph persistence. The project explicitly requires LCEL history and
excludes LangGraph orchestration. A narrowly scoped compatibility adapter suppresses
only that known constructor notice; it does not hide other warnings. This remains
a deliberate migration task for a future architecture revision.

## Scoring and adaptation

The evaluator judges correctness, reasoning, applied relevance, and clarity without
penalizing concise correct answers. Behavioral coaching asks for context, actions,
and outcomes. Incorrect answers and "I don't know" are still evaluated; unrelated
action requests receive a return-to-interview message without advancing the turn.

Malformed output and transient failures get bounded attempts. Provider HTTP 400
responses can move directly to the stricter JSON fallback; authentication and rate
limits stop further paid attempts for that evaluation. Exhaustion records score 5,
an apology, and `evaluation_status=defaulted`. Defaulted scores never adapt difficulty.
Valid scores below 4 move one level down, above 8 move up, and 4-8 remain unchanged.
Only the evaluated skill changes. Target difficulty stays fixed for the confirmed JD.

The next exact question is selected only when it will be displayed. Candidates must
match the planned skill and current practice difficulty and pass asked-question
exclusions. Selection considers JD word overlap and topic diversity. If no unused
candidate remains, the service generates replacements from JD/cached research;
that path never invokes Tavily. Generic fallback questions are disclosed and have
heuristic, uncalibrated difficulty. If novelty cannot be maintained, the service
returns a recoverable error instead of silently repeating.

## Evidence reports

Reports run only at the round completion boundary. Three independent textual
branches and an application-owned arithmetic branch execute via `RunnableParallel`.
Every textual branch is Pydantic-validated and has its own bounded fallback. Branch
failures use evidence-based deterministic text so the numeric report survives.

`overall_score` is the unrounded mean of all stored evaluations, including defaulted
5 values. The UI rounds only for display and discloses the defaulted count. Reliable
per-skill averages exclude defaults. All-default reports label readiness unavailable.
Fewer than two valid observations means insufficiently assessed. Observed difficulty,
fixed JD target, target gaps, and omitted initial skills remain visible. Scores across
difficulties are not a calibrated measure of hireability.

## Practice and fresh retries

Focused practice offers 3, 5, or 10 questions on suggested gaps, including omitted or
insufficiently assessed skills. It retains the session, lineage, evidence, fixed target,
research cache, and search counters. Only the round's progress and report reset.
Later reports summarize cumulative stored evidence and earlier reports remain in
session memory. No practice action expands the existing search allowance.

A fresh interview retains the confirmed JD, initial plan, and lineage exclusions,
but receives a new session ID, empty history/ledger/usage/cache, and a fresh search
budget. Questions shown before an interruption are still excluded. A new job
description instead receives an unrelated lineage and isolated state.

## Usage and privacy

LangChain callbacks count attempted LLM requests, errors, and provider-reported input
and output tokens by stage. Retry/fallback/default totals survive activity-log trimming. Missing usage metadata is not guessed. Tavily counters
include failed invocations. Activity events contain safe metadata, not raw provider
payloads, keys, JD text, or answers. Answers are intentionally retained in the
in-memory evaluation/history stores for coaching and are sent to Groq on evaluation.

No dollar price is inferred. Check current Groq/Tavily billing and measured usage
before estimating cost. Tests and the offline demo do not call paid providers.
