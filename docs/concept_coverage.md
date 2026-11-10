# Milestone and concept coverage

| Milestone | Implementation | Verification |
|---|---|---|
| 1. Foundation | Config, models, stores, uv src layout | Contract/config/isolation tests |
| 2. JD parsing | Separate prompts, structured parser, correction UI | Parser success/failure and review checks |
| 3. Coverage | Fixed count formula, selected/omitted skills, deterministic fallback | Allocation boundaries and planner/UI tests |
| 4. Research | Validated tool calls, Tavily one-shot budget/cache, provenance | Fake HTTP, tool-ID, exclusion, outage and UI tests |
| 5. Interview | Stable turn IDs, staged history, application ledger | Duplicate/concurrent submission and history tests |
| 6. Evaluation | Rubric, strict score contract, JSON fallback, marked neutral 5 | Malformed output, 400/429, attempt-count tests |
| 7. Adaptation | Per-skill RunnableBranch and 3/5/10-question practice | Threshold/boundary, target preservation, no-search tests |
| 8. Report | RunnableParallel, deterministic mean, validated branch fallbacks | Exact arithmetic, all-default, omitted/low-level evidence tests |
| 9. Retry/usage | Lineage exclusions, new IDs/budgets, activity, usage callbacks | Unanswered-question exclusion, reset, callback and UI tests |
| 10. Release | Offline demo, docs, locked install, GitHub CI | Complete UI/demo integration checks and lint/format suite |

| Required concept | Location |
|---|---|
| ChatPromptTemplate and structured output | chains/jd_parser.py, planner.py, research.py, evaluator.py, report.py |
| LCEL RunnableSequence via `\|` | All chain factories |
| RunnableWithMessageHistory | chains/evaluator.py (staged history adapter) |
| RunnableBranch | chains/adaptation.py |
| RunnableParallel | services/reporting.py |
| External tools and controlled execution | chains/research.py and services/research.py |
| Bounded attempts, parser fallback, safe defaults | services/validated_call.py, evaluation.py, research.py |
| Context and guardrails | Confirmed skill authorization, bounded snippets/history, source evidence, exclusions |

Automated tests cover implementation behavior with fake providers. Live provider
availability, account quotas, and real-world evaluation quality remain separate
verification concerns; see the current validation notes and demo guide.
