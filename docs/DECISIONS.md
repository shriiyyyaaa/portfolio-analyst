# Decision log

| # | Decision | Why | Trade-off / what I'd revisit |
|---|---|---|---|
| 1 | **SQL (SQLite) instead of RAG / vector search** | Data is small, structured and needs exact aggregation (sums, group-by, filters). Vector search would add approximate retrieval to a problem that needs exact answers. | SQLite is single-writer, single-instance. Move to Postgres for scale or multi-instance deployment (one `DATABASE_URL` change). |
| 2 | **Single agent with tools, custom tool-calling loop; no LangChain/LangGraph** | The flow is one loop: model → tools → model. Hand-written it is ~80 lines, fully visible in logs, and easy to explain. A framework adds abstraction without adding capability here. | No built-in graph/state tooling. If workflows grow (approvals, multi-agent), LangGraph would earn its place. |
| 3 | **All maths in deterministic tools, never in the model** | LLMs mis-add. Tools give exact, testable numbers (`test_tools.py`). The model only selects tools and narrates. | More tool schemas to maintain; the model must choose the right tool. |
| 4 | **`user_id` injected server-side; ownership check on writes** | The model can hallucinate or be prompted; it must not be able to touch another user's data. | Chat itself has no login: anyone can pick a user in the demo UI. Real deployment needs auth. |
| 5 | **Normalise "Commercial Office" and "Office" into one `Office` category** | Same asset class labelled inconsistently (P002/P007/P008 vs P011). Raw labels kept in the DB; analytics use `normalized_type`. | Mapping is a hand-written dict in `normalization.py`; unknown labels pass through unchanged. |
| 6 | **`purchase_price_inr` stays NULL, never 0; no appreciation answers** | Blank cost basis and no dates: any appreciation figure would be invented. Agent says it cannot be calculated. Yield = current gross yield only. | Users can't get gain/appreciation until purchase price and date are captured (could be asked conversationally). |
| 7 | **Hypotheticals via read-only `simulate_exclusion`** | Keeps "what if" separate from real data by construction: the tool has no write path. | Only exclusion is a first-class tool. Other what-ifs (e.g. "what if I add X") rely on the model reasoning over tool results, which is less rigorous. |
| 8 | **Writes execute immediately, no confirmation step** | Matches the brief's simple examples; fewer turns; lower latency. The agent confirms the change afterwards. | A mis-parsed value is written before the user can object. Production: propose → confirm → commit, plus an audit trail. |
| 9 | **Send only final assistant text as history (last 10 messages), not raw tool JSON** | Keeps tokens (and latency/cost) roughly constant as conversations grow. | Follow-ups that need exact earlier numbers must re-call a tool; very long chats lose early context. |
| 10 | **Single model via OpenRouter (`openrouter/free`), no routing** | Zero cost while building. Model is one env var. | Free tier is slow (6 to 20 s per turn observed, see docs/LATENCY.md) and can vary between calls. For production: route simple lookups to a small fast model, comparisons/what-ifs to a stronger one, with fallback on error. |
| 11 | **Observability = two DB tables + admin UI** | Every tool and model call (args, result, latency, tokens, error) is stored; the admin UI just reads them. No extra infra. | No aggregation dashboards, alerting or tracing tool (Langfuse etc.). |
| 12 | **Admin auth: one shared password, stateless HMAC token (8 h)** | The brief calls it "simple, not a CRM". No session table or accounts needed. | No hashing, rate limiting, per-admin identity or audit trail. Real product: per-admin accounts behind an identity provider. |
| 13 | **"Needs attention" = tool failure or iteration cap** | Cheap, objective, explainable triggers. | Misses silent bad answers, user frustration, and explicit requests for a human. |
| 14 | **Admin UI lives in the same React app at `/admin`** | One deploy, one build, no router dependency for two screens. | Admin code ships in the user bundle (still gated by the API). |
| 15 | **Plain httpx to OpenRouter instead of an SDK** | One fewer dependency; exact control over what is timed and logged. | Manual handling of the OpenAI-compatible response format. |
| 16 | **Postgres in production, SQLite locally, chosen by `DATABASE_URL`** | Free hosts have ephemeral disks, so SQLite would lose conversations and logs on every restart. Same code, different URL. | Needs an external database account (Neon). The dataset is seeded only into an empty database so restarts never overwrite chat edits. |
| 17 | **Model resilience: one retry, optional fallback model, friendly message and a Needs-attention flag** | A public demo cannot return a raw 500 when a free model rate-limits. | Failed model calls are not stored in `model_calls` (the reason is on the conversation). A write that succeeded before the model failed can look like a failure, so the message warns about it. |

## Known limitations
- Model errors: one retry, then the optional `FALLBACK_MODEL`, then a friendly message plus a Needs-attention flag. Not covered: a model that answers badly rather than failing.
- OpenRouter `:free` models are capped at 50 requests/day per account until $10 of credits have ever been bought (then 1,000/day). A chat turn uses 2 to 3 requests, so a public demo on the unfunded tier runs out after roughly 20 turns a day.
- Free-tier latency is high and variable; free models occasionally skip tool use.
- No streaming: the UI shows "typing…" until the full answer is ready.
- No chat authentication, no rate limiting, CORS is wide open (dev setting).
- Only one hypothetical tool (exclusion). No "what if value changes" tool.
- Agent behaviour rules in the system prompt are soft: they depend on the model.
- SQLite file is not suitable for multiple app instances.

## External dependencies
OpenRouter API (model gateway). No other external services. All data is the provided synthetic dataset.

## Issues found in testing (via the admin dashboard) and what changed
| Finding | Cause | Fix (Step 7) |
|---|---|---|
| Asked "Which properties do I own in Mumbai?" by a Delhi NCR owner, the agent correctly found 0, then **invented** that the portfolio was in Bengaluru and Delhi. Real locations: Gurugram and Noida. | No tool exposed a location breakdown, so the model filled the gap. | `portfolio_summary` now returns `by_city` with localities. A GROUNDING rule in the system prompt says to state location, occupancy, tenant or rent only when a tool returned it. |
| Segment yields (4.7%, 7.3%, 5.4%) were computed by the model. They happened to be right, but that breaks decision 3. | Tools returned value and rent per type but not yield. | Gross yield is precomputed overall, per type and per city. |
| After adding a property the agent said it was "marked as vacant/self-occupied". | Occupancy is actually unset for created properties; the agent inferred it from rent = 0. | GROUNDING rule. Remaining gap: `create_property` does not ask for occupancy or rent. |
| Turn D needed 3 model calls for 2 tools. | Tools were requested one at a time. | Not fixed; listed in docs/LATENCY.md as future work. |

**Data quirk:** the dataset has no city column and Alibaug is written "Alibaug, Maharashtra", so `by_city` groups it under "Maharashtra". Documented rather than special-cased.

**Still true:** the GROUNDING rule is a soft, model-dependent control. Removing the reason to guess (the tool now returns the data) is the stronger fix.

### Found on re-test (after the Step 7 fix)
- "Where are my properties located?" now returned the right cities, values, shares and localities, but labelled Gurugram "2 (Office)" and Noida "1 (Retail)". Truth: Gurugram is 1 Office + 1 Retail, Noida is 1 Office. Cause: `by_city` carried no per-type data, so the model guessed, probably anchored on earlier wrong replies. Fix: `by_city` now includes `types`.
- Because history replays earlier assistant text, one wrong answer can be repeated later as if it were fact (the earlier "Bengaluru" claim kept resurfacing in the same conversation). Mitigations: tools return the data, the GROUNDING rule, and a **New chat** button. Not solved: a structured facts memory, or re-verifying replayed numbers.
