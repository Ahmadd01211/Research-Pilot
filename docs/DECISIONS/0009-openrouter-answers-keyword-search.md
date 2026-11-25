# ADR 0009 — OpenRouter answers, shared daily budget, keyword retrieval

Accepted 24 November 2026. Partly supersedes ADR 0007, which assumed Google for both
embeddings and answers.

## Context

The user chose OpenRouter's free tier for answers, with about 20 requests a day. Retrieval
previously required hosted embeddings. Indexing one 41-page paper takes about 48 embedding
calls, so embeddings cannot share a 20-calls-a-day budget.

## Decision

- **Answer provider is configurable**: `RP_ANSWER_PROVIDER=google|openrouter`. OpenRouter
  uses `/api/v1/chat/completions` with a server-only key, temperature 0, and a JSON-object
  response. The existing citation contract stays authoritative: every statement must cite
  only retrieved source IDs, abstention discards uncited text, and anything else is a 502.
  Free models vary in structured-output support, so the schema is enforced server-side,
  accepting at most a Markdown code fence around the JSON.
- **Shared daily budget**: `RP_ANSWER_DAILY_LIMIT` (default 20) is enforced app-wide by an
  atomic Redis script keyed by provider and UTC day. A slot is reserved just before the
  provider call and never refunded, because a failed request may still count against the
  provider's quota. A question with no retrieved evidence makes no provider call and spends
  nothing. The per-user rate limit (10 per 15 minutes) still applies.
- **Retrieval without embeddings**: when embeddings are off, search uses PostgreSQL
  full-text search (English stemming, OR-combined terms, cover-density ranking) over each
  paper's current-version chunks. That is the same lexical arm the hybrid search already
  fuses with vectors. A paper is reported "Keyword-searchable" exactly when current chunks
  exist; no index is claimed. With embeddings on, behaviour is unchanged (hybrid RRF).

- **Fairness**: `RP_ANSWER_USER_DAILY_LIMIT` caps each researcher's share of the daily
  budget. It is checked and incremented with the global counter in one Lua script, so a
  refused attempt reserves nothing. Unset means the whole budget, which is right for a
  single user. **Set it lower before opening registration**, or one account can exhaust
  everyone's answers in about 30 minutes under the 10-per-15-minute rate limit.
- **Data policy**: by default the OpenRouter request carries
  `provider: {"data_collection": "deny"}`, so routing uses only model hosts that do not
  collect prompts. Some free models have no such host; OpenRouter then returns 404, which
  is reported as a configuration problem. `RP_OPENROUTER_ALLOW_DATA_COLLECTION=true` lifts
  this. The chat then warns that free hosts may retain or train on prompts.
- **Resilience**: keyword search does not depend on Redis. If Redis is down,
  capabilities report the remaining allowance as unknown instead of failing the page.
  Answers still require Redis, because the budget is not enforceable without it.
- Counters are keyed by provider and UTC day. Changing the key or model mid-day does not
  reset them (conservative).

## Consequences

- Research Chat works with only an OpenRouter key; paper text never goes to an embedding
  provider. The question and up to 8 retrieved passages do go to the answer provider; the
  UI says so next to the remaining-answer count.
- Keyword search misses paraphrases and synonyms. Users are told to use the paper's terms.
  Semantic retrieval (a local embedding model, ANN index choice such as HNSW or IVF-PQ)
  belongs to the RAG-refinement phase.
- Full-text search computes `to_tsvector` per query. That is fine at about 10 papers × a
  few hundred chunks; a stored tsvector with a GIN index is the obvious next step at scale.
- Free-model output quality and real quota behaviour are unverified until a real key is
  configured. Tests use a mock transport only.
