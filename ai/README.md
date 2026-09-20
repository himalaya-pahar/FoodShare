# FoodShare AI Assistant — module guide

This package implements the **v1 RAG-based AI Assistant** for the FoodShare
backend. It is mounted into the existing FastAPI app and exposes:

- `POST /ai/chat` — answer a question about how to use FoodShare.

It is **read-only**. It must never create donations, request pickups, approve
accounts, or change application state. See `workspace_ai_implementation/CONTEXT.md`
for the design briefing and `workspace_ai_implementation/REGISTRY.md` for the
file-level registry.

---

## Architecture in one minute

```
React Native client
   │ Bearer JWT
   ▼
FastAPI app ──► ai/api/routes.py     (POST /ai/chat, requires CurrentUserDep)
                │
                ▼
              ai/repository/ai_service.py    (orchestrator)
                │
                ├──► ai/retrieval/query_rewrite.py   (heuristic + LLM fallback)
                ├──► ai/retrieval/retriever.py       (embed → top_k → hits)
                │       │
                │       ├──► ai/retrieval/embedder.py (local sentence-transformers, 384d)
                │       └──► ai/retrieval/vector_store.py (Supabase pgvector)
                ├──► ai/generation/prompt.py + llm.py (LLMProvider ABC; default = Gemini)
                ├──► ai/generation/answer_parser.py   (sources + safe-fallback)
                ├──► ai/guardrails/scope_check.py     (in/out-of-domain)
                └──► ai/repository/sessions.py        (60-min in-memory TTL)
```

The whole AI module is optional — if anything is misconfigured, the
orchestrator returns a controlled fallback message and never raises to the
user. The regular FoodShare API keeps working unchanged.

---

## Environment variables

All config is read from `config.py`, which loads `.env`. Add these to your
local `.env` (do **not** commit real keys):

```env
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.5-flash-lite
GEMINI_API_KEY=...
EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2
AI_TOP_K=5
AI_SIMILARITY_THRESHOLD=0.55
AI_CHUNK_SIZE=800
AI_CHUNK_OVERLAP=120
AI_SESSION_TTL_MINUTES=60
AI_SESSION_MAX_TURNS=6
AI_DEBUG_LOG_CONTENT=false
```

See `.env.example` at the project root for the full set.

---

## First-time setup

```bash
# 1. Install the new dependencies
pip install -r requirements.txt

# 2. Reindex the knowledge base. The script first calls
#    ai.setup_db.ensure(), which:
#      a) issues `CREATE EXTENSION IF NOT EXISTS vector;`, and
#      b) creates the `ai_chunks` table with a `VECTOR(384)` column.
#    It then loads every .md in ai/knowledge_base/, chunks, embeds, and
#    stores the result in your Supabase Postgres via pgvector.
python scripts/reindex_kb.py
```

You don't need `psql` for this — your Supabase-hosted Postgres accepts the
same SQL through the project's SQLAlchemy engine. (If you ever *do* want to
run the raw SQL outside Python, `scripts/enable_pgvector.sql` has it; just
execute it from the Supabase SQL editor in the dashboard.)

You should see output like:

```text
Loaded 5 document(s) from knowledge base.
Produced 73 chunk(s).
  indexed 32/73
  indexed 64/73
  indexed 73/73
Done. Indexed 73 chunks from 5 documents in 24.6s.
```

## Running the server

Nothing changes about how you start the API. The AI router is mounted the
same way as every other router:

```bash
uvicorn main:app --reload
```

Open `http://localhost:8000/docs`, authorize with any approved user's JWT,
then expand the **AI Assistant** tag and try:

```json
{
  "session_id": null,
  "message": "How does an NGO request a pickup?"
}
```

Follow-up with the returned `session_id`:

```json
{
  "session_id": "<from previous response>",
  "message": "What happens after the restaurant accepts it?"
}
```

## Switching the LLM provider

`LLM_PROVIDER` selects which subclass of `LLMProvider` is used.

- **Default (Gemini):** `LLM_PROVIDER=gemini`, set `GEMINI_API_KEY`.
- **Adding a new provider** (e.g. OpenAI):
  1. Create a new class in `ai/generation/llm.py` implementing `LLMProvider`.
  2. Register it: `_PROVIDERS["openai"] = OpenAIProvider`.
  3. Set `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4o-mini`, `OPENAI_API_KEY=...`.

No other code changes.

## Rebuilding the knowledge base

Whenever you add or change anything in `ai/knowledge_base/`:

```bash
python scripts/reindex_kb.py
```

This drops the existing rows and re-embeds every chunk. Safe to rerun.

## Running tests

```bash
pip install pytest
pytest ai/tests -v
```

These are offline and use stub `EmbeddingProvider` / `VectorStore`. No
network or DB required.

## Evaluating retrieval quality

```bash
python -m ai.evaluation.evaluate
```

Reports retrieval hit-rate (top-1 document for in-domain questions) and
scope refusal accuracy (out-of-domain questions refused). Does **not** call
the LLM, so it is free to run after every reindex.

## How multi-turn chat works

- The client sends a `session_id`. If absent, the server creates one and
  returns it. The same id must be passed back on follow-ups.
- The server keeps the last `AI_SESSION_MAX_TURNS * 2` messages per
  `(user_id, session_id)` tuple in memory (no DB writes).
- Sessions are dropped after `AI_SESSION_TTL_MINUTES` of inactivity.
- On a follow-up, the *query rewrite* layer reconstructs the standalone
  question (heuristic by default; LLM fallback when the heuristic looks
  weak) so retrieval doesn't lose the thread.

## Safety + scope

- The assistant is restricted to "how to use FoodShare" via
  `ai/guardrails/scope_check.py`.
- Out-of-domain questions return the controlled refusal without an LLM
  call.
- The system prompt forbids invention and forces it to cite sources or
  admit "I could not find enough information".
- `ai/guardrails/output_validation.py` redacts leaked credentials and
  detects drift back into off-topic content.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `503 temporarily unavailable` from `/ai/chat` | LLM key missing/invalid, embedding model not downloaded yet, or Supabase unreachable | Check env vars and provider quotas |
| Index returns `0 chunks` after reindex | KB folder missing or empty | `ls ai/knowledge_base/` should show 5 `.md` files |
| "Out of domain" on a legitimate question | `IN_DOMAIN_KEYWORDS` doesn't cover the phrasing | Add the term to the list in `ai/guardrails/scope_check.py` |
| LLM answer ignores retrieved context | Provider ignoring system prompt | Lower temperature, increase `max_tokens` |
| pgvector extension error | Extension not enabled | `psql -c 'CREATE EXTENSION IF NOT EXISTS vector;'` |

---

## Out of scope for v1

- Streaming responses
- Persistent conversation memory
- Hybrid retrieval / reranking / agentic RAG
- The React Native chat screen (deliver the API; the client team owns UI)

These are intentionally listed here so a future agent does not accidentally
start implementing them.

## Key files to read first

1. `ai/repository/ai_service.py` — the orchestrator, end-to-end flow.
2. `ai/generation/llm.py` — LLM provider abstraction.
3. `ai/retrieval/retriever.py` + `vector_store.py` — retrieval pipeline.
4. `ai/guardrails/scope_check.py` — what counts as "in-domain".
5. `../workspace_ai_implementation/CONTEXT.md` — project briefing.
