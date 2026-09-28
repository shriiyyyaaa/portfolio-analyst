# Latency

## Method
Six real turns from the admin dashboard, across three different users' conversations, on the free tier (`openrouter/free`, which resolved to `nvidia/nemotron-3-ultra-550b-a55b:free` for all 13 model calls). Tool time is measured around `execute_tool`; model time is measured around the HTTP call to OpenRouter (`llm_client.py`). Both are stored per call in `tool_calls` / `model_calls`.

"End to end" below means model time + tool time. Browser-to-API transfer, database writes of the logs and UI rendering are not measured; they are local and small next to the model.

**Caveat:** six turns on a shared free tier is a small sample. It supports the shape of the result (the model dominates everything) but not a p95.

## Results
| Turn | Question | Tools | Model calls | Model time | Tool time | End to end |
|---|---|---|---|---|---|---|
| A | Add a 5,000 sq ft retail property in Bandra worth ₹12 Cr | create_property | 2 | 14.9 s | 31 ms | **15.0 s** |
| B | What does my portfolio look like (after the add) | portfolio_summary | 2 | 6.7 s | 14 ms | **6.7 s** |
| C | What is my total portfolio value? | portfolio_summary | 2 | 9.5 s | 14 ms | **9.6 s** |
| D | Compare my residential and commercial exposure | search_properties + portfolio_summary | 3 | 20.2 s | 0 ms | **20.2 s** |
| E | Which properties do I own in Mumbai | search_properties | 2 | 5.8 s | 0 ms | **5.8 s** |
| F | What does my portfolio look like? (first message) | portfolio_summary | 2 | 17.2 s | 0 ms | **17.2 s** |

- **Typical:** median **12.3 s**, mean 12.4 s, range 5.8 to 20.2 s.
- Single-tool read questions (B, C, E, F): median 8.2 s.
- **Where the time goes:** model 74.3 s vs tools 59 ms in total, so tools are 0.08% of the time. Average model call: 5.7 s.
- **Tokens:** 29,140 prompt vs 1,867 completion (15.6 : 1). Every call re-sends about 1,960 fixed tokens (system prompt plus the 8 tool schemas).

## Per model call
| # | Turn | Role | ms | Prompt tok | Completion tok | Output tok/s |
|---|---|---|---|---|---|---|
| 1 | A | decide | 12,672 | 2,003 | 415 | 33 |
| 2 | A | answer | 2,266 | 2,232 | 63 | 28 |
| 3 | B | decide | 1,625 | 2,040 | 38 | 23 |
| 4 | B | answer | 5,110 | 2,245 | 255 | 50 |
| 5 | C | decide | 1,843 | 1,963 | 38 | 21 |
| 6 | C | answer | 7,702 | 2,224 | 170 | 22 |
| 7 | D | decide | 6,827 | 2,316 | 138 | 20 |
| 8 | D | decide | 5,500 | 2,370 | 66 | 12 |
| 9 | D | answer | 7,827 | 2,584 | 262 | 33 |
| 10 | E | decide | 3,562 | 2,514 | 61 | 17 |
| 11 | E | answer | 2,203 | 2,569 | 78 | 35 |
| 12 | F | decide | 2,061 | 1,963 | 50 | 24 |
| 13 | F | answer | 15,140 | 2,117 | 233 | 15 |

"decide" = the call returned a tool request; "answer" = the final narration. Turn D's second call is classed "decide" because it made 3 model calls for 2 tool runs (inferred from the counts).

## Why a response takes this long
1. **A tool-using answer needs at least two sequential model calls.** Call 1 reads the question and picks a tool; the tool runs (0 to 31 ms); call 2 reads the result and writes the answer. Call 2 cannot start before the tool finishes, so the trip cannot be parallelised.
2. **Extra tool rounds cost a full model call each.** Turn D was the slowest (20.2 s) because the model called `search_properties`, then `portfolio_summary`, one at a time, giving 3 calls. It could have requested both together.
3. **The free tier adds large variance.** Turns B and F are the same question from the same user with the same tool. B took 6.7 s, F took 17.2 s. The final calls produced similar output (255 vs 233 tokens) at 50 vs 15 tokens/s. Nothing in our code differs, so this is queueing on the shared free endpoint.
4. **Output length matters less than expected.** Turn A's first call spent 12.7 s and 415 completion tokens on what is a very short tool request. That is consistent with hidden reasoning tokens (an inference: the gateway reports only the count).

## What I did to reduce unnecessary latency
- **Deterministic tools in the same process:** 12 rows in SQLite, so 0 to 31 ms. Nothing to optimise there.
- **History is final text only, last 10 messages**, never raw tool JSON, so prompts stay at about 2.0 to 2.6k tokens however long the chat gets.
- **Hard cap of 4 model calls per message** bounds the worst case.
- **Precomputed answers in the tool result (added in Step 7):** per-type and per-city yield, shares and localities now come from `portfolio_summary`, so segment and location questions no longer need an extra lookup or model arithmetic. Not yet re-measured.
- **"Analyst is typing…" indicator** to make the wait legible. There is no streaming yet.

## What I would change at significantly higher volume
| Change | Effect |
|---|---|
| Paid, fast model with routing: a small model for single-tool lookups, a stronger one for comparisons and what-ifs, plus a fallback model on error or timeout | Biggest win: removes the free-tier queue and variance. Not measured here. |
| Stream the final answer (SSE) | Perceived latency becomes time-to-first-token instead of full completion. |
| Skip call 1 for the most common intents (total value, portfolio overview) with a deterministic router, then use the model only to narrate | One model call instead of two for the commonest questions. |
| Encourage parallel tool calls and run them concurrently | Removes extra rounds like turn D. |
| Prompt caching for the fixed ~1,960-token prefix | Input tokens dominate (16 : 1), so this cuts cost and time-to-first-token. |
| Cache `portfolio_summary` per user, invalidate on writes | Writes are rare, reads are repeated. |
| Async endpoints and async HTTP client | Today each in-flight chat holds a worker thread for 6 to 20 s. |
| Postgres with pooling; move log writes to a background task or queue | SQLite is single-writer and single-instance. |
| Timeouts, retries, circuit breaker, per-user rate limits | Reliability. Today a failed model call returns a server error. |
| p50/p95 dashboards from `model_calls` | The data is already collected. |
