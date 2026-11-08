# AI Document Analyzer — Backend

FastAPI service that turns a document (meeting transcript, project brief, report, notes) into a
validated, structured analysis: **summary**, **key points**, **action items** and **open
questions**. Results are stored in SQLite and served over a REST API to the React frontend
(`http://localhost:5173`).

## Overview and architecture

```
HTTP ──> middleware (CORS → request ID → access log → body limit → error catch-all)
     ──> api/        routes + dependency wiring, consistent JSON error envelope
     ──> services/   AnalysisService: input checks → prompt → provider (retries) →
                     JSON extraction → schema validation (+1 repair) → persist
     ──> providers/  LLMProvider interface: MockProvider | OpenAICompatibleProvider
     ──> db/         sqlite3 + AnalysisRepository (parameterized SQL, one table)
domain/   Pydantic models (the AI output contract) and the typed AppError hierarchy
prompts/  versioned system / user / repair prompts (PROMPT_VERSION = analysis-v1)
```

Only `app/providers/openai_compatible.py` imports the `openai` SDK. The service depends only on
the `LLMProvider` protocol. No unvalidated LLM output reaches the database or the client.

## Quick start (mock mode — no API key, no network)

```bash
cd backend
make install
make run
```

Open http://localhost:8000/api/docs. Without `make`:

```bash
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload --port 8000
```

## Running with Groq

Create `backend/.env` (never commit it):

```
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=<your Groq key>
LLM_MODEL=<model ID from the Groq console>
```

Then `make run`. Startup fails with a clear message naming any missing variable; the key's value
is never printed. `GET /api/health` shows the active provider and model.

## Switching to another OpenAI-compatible provider

Change only environment variables — no code changes:

| Provider | `LLM_BASE_URL` |
| --- | --- |
| Groq | `https://api.groq.com/openai/v1` |
| xAI Grok | `https://api.x.ai/v1` |
| Google Gemini (OpenAI endpoint) | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| OpenRouter | `https://openrouter.ai/api/v1` |
| Ollama (local) | `http://localhost:11434/v1` (any non-empty `LLM_API_KEY`) |

Set `LLM_API_KEY` and `LLM_MODEL` for that provider. If it rejects `response_format`, the
provider retries once without it and stops sending it for the rest of the process.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development` | `development`, `test` or `production` |
| `LLM_PROVIDER` | `mock` | `mock` or `openai_compatible` |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | Any OpenAI-compatible endpoint |
| `LLM_API_KEY` | empty | Required when provider is `openai_compatible` |
| `LLM_MODEL` | empty | Required when provider is `openai_compatible` |
| `LLM_TIMEOUT_SECONDS` | `30` | Per-call timeout |
| `LLM_TEMPERATURE` | `0.2` | Low, for consistent structure |
| `LLM_MAX_OUTPUT_TOKENS` | `2048` | Output cap |
| `LLM_JSON_MODE` | `true` | Send `response_format={"type": "json_object"}` |
| `LLM_MAX_TRANSIENT_RETRIES` | `2` | Retries for rate limits, timeouts and outages |
| `LLM_MAX_REPAIR_ATTEMPTS` | `1` | Corrective retries for malformed output |
| `LLM_TOTAL_BUDGET_SECONDS` | `90` | Wall-clock cap across all attempts of one request |
| `LLM_MAX_RETRY_AFTER_SECONDS` | `10` | Longest provider `Retry-After` wait honoured before giving up (Groq free tier: use 30) |
| `LLM_REASONING_EFFORT` | *(blank)* | `low` / `medium` / `high` for reasoning models such as gpt-oss; dropped automatically if the provider rejects it |
| `LLM_ENABLE_INTELLIGENCE` | `true` | Run the contradiction, risk and dependency pass after extraction |
| `CROSS_DOC_CONTEXT_LIMIT` | `5` | How many earlier analyses are compared for cross-document contradictions |
| `MAX_TITLE_CHARS` | `200` | Title limit |
| `MAX_INPUT_CHARS` | `50000` | Text limit |
| `MAX_BODY_BYTES` | `262144` | Request body limit (256 KB) |
| `DATABASE_PATH` | `./data/analyses.db` | SQLite file; folder created if missing |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list |
| `MOCK_LATENCY_MS` | `300` | Simulated delay in mock mode |
| `LOG_LEVEL` | `INFO` | Logging level |

## Analysis pipeline (v2)

Each `POST /api/analyses` runs three stages:

1. **Extraction** (one LLM call, `analysis-v2` prompt): summary, key points, entities (people, organizations, dates, locations, technologies, monetary values, important terms), action items (owners, deadline + confirmed/tentative, status, priority + stated/inferred, certainty, evidence quote), decisions (confirmed / proposed / rejected / pending / changed) and categorized open questions.
2. **Intelligence** (one LLM call, `app/intelligence/`): three independent modules — contradictions (within the document and against the last `CROSS_DOC_CONTEXT_LIMIT` analyses), risks (stated vs AI-inferred, with inferred severity labelled as such) and dependencies. Each module's section is parsed separately, so one bad section never breaks the others. If the whole pass fails, the extraction is still saved with `intelligence.status = failed`, and `POST /api/analyses/{id}/intelligence` re-runs it (also useful after adding newer documents).
3. **Validation** (deterministic, no LLM, `app/intelligence/validation.py`): checks every evidence quote against its source document, removes owners, deadlines and entities that do not appear in the text, checks calendar dates and normalizes full dates to ISO, merges duplicate tasks and decisions, drops contradictions without two quote-backed different values and dependencies without support, labels items as fact / inference / assumption, and adds open questions for missing owners, deadlines, unresolved decisions and approvals. Everything it changed is listed in `result.validation`.

All new fields are additive: `owner`, `due_date`, `priority` and `open_questions` (list of strings) keep their meaning, and records saved before v2 still load.

## API endpoints

All routes are under `/api`. Swagger: `/api/docs`. OpenAPI: `/api/openapi.json` (every route
declares its response model and `ErrorResponse`, so TypeScript types can be generated).

| Method | Path | Success | Errors |
| --- | --- | --- | --- |
| POST | `/api/analyses` | 201 + `AnalysisRecord`, `Location` header | 413, 422, 429, 502, 503, 504 |
| GET | `/api/analyses?limit=20&offset=0` | 200 + `AnalysisListResponse` (limit 1–100, newest first) | 422 |
| GET | `/api/analyses/{id}` | 200 + `AnalysisRecord` | 404 (also for a malformed ID) |
| DELETE | `/api/analyses/{id}` | 204 | 404 |
| POST | `/api/analyses/{id}/intelligence` | 200 | 404, 429, 502, 503, 504 |
| GET | `/api/health` | 200 + `HealthResponse` | — |

```bash
curl -X POST http://localhost:8000/api/analyses \
  -H "Content-Type: application/json" \
  -d '{"title": "Sprint planning", "text": "Meeting transcript... Priya will draft pricing by Friday."}'
```

```bash
curl "http://localhost:8000/api/analyses?limit=10&offset=0"
```

```bash
curl http://localhost:8000/api/analyses/<id>
```

```bash
curl -X DELETE http://localhost:8000/api/analyses/<id>
```

```bash
curl http://localhost:8000/api/health
```

Every response carries `X-Request-ID` (send your own, up to 64 chars of `[A-Za-z0-9-]`, or one
is generated).

## Error codes

Every error uses one envelope:

```json
{"error": {"code": "RATE_LIMITED", "message": "The AI service is busy. Please wait a moment and try again.",
           "retryable": true, "request_id": "3f1c...", "details": null}}
```

| Code | HTTP | Retryable | When |
| --- | --- | --- | --- |
| `EMPTY_INPUT` | 422 | No | Title or text empty after trimming |
| `INPUT_TOO_LONG` | 422 | No | Title > `MAX_TITLE_CHARS` or text > `MAX_INPUT_CHARS` |
| `VALIDATION_ERROR` | 422 | No | Wrong types, missing fields, bad query params (`details`: `[{field, reason}]`) |
| `PAYLOAD_TOO_LARGE` | 413 | No | Body > `MAX_BODY_BYTES` |
| `NOT_FOUND` | 404 | No | Unknown or malformed analysis ID, unknown route |
| `METHOD_NOT_ALLOWED` | 405 | No | Wrong HTTP method for a route |
| `CONTEXT_TOO_LONG` | 422 | No | Model's context window exceeded |
| `MALFORMED_AI_RESPONSE` | 502 | Yes | Output unreadable after the repair attempt |
| `RATE_LIMITED` | 429 | Yes | Provider rate limit (`Retry-After` header when known) |
| `PROVIDER_TIMEOUT` | 504 | Yes | Provider took too long |
| `PROVIDER_UNAVAILABLE` | 503 | Yes | Connection failure or provider 5xx |
| `PROVIDER_AUTH_ERROR` | 502 | No | Bad or unauthorized API key |
| `PROVIDER_ERROR` | 502 | No | Provider rejected the request (e.g. unknown model) |
| `INTERNAL_ERROR` | 500 | No | Any unhandled exception (traceback logged, never returned) |

## Mock trigger tokens

In mock mode, put a token anywhere in the document text to reproduce a path from the UI:

| Token | Behavior | Result |
| --- | --- | --- |
| `[[mock:fenced]]` | Valid JSON inside triple-backtick `json` fences | 201 |
| `[[mock:malformed]]` | Always non-JSON prose | 502 `MALFORMED_AI_RESPONSE` |
| `[[mock:malformed_once]]` | Non-JSON first, valid on the repair call | 201 (repair used) |
| `[[mock:invalid_schema]]` | Valid JSON missing `summary` | 502 `MALFORMED_AI_RESPONSE` |
| `[[mock:ratelimit]]` | `RateLimitError(retry_after_seconds=2)` | 429 + `Retry-After: 2` (after retries) |
| `[[mock:timeout]]` | `ProviderTimeoutError` | 504 (after retries) |
| `[[mock:unavailable]]` | `ProviderUnavailableError` | 503 (after retries) |
| `[[mock:auth]]` | `ProviderAuthError` | 502 `PROVIDER_AUTH_ERROR` |
| `[[mock:context]]` | `ContextLengthError` | 422 `CONTEXT_TOO_LONG` |
| `[[mock:intel_malformed]]` | Extraction succeeds; the intelligence pass returns prose | 201 with `intelligence.status = failed` |
| `[[mock:intel_ratelimit]]` | Extraction succeeds; the intelligence pass is rate limited | 201 with `intelligence.status = failed` |
| `[[mock:conflict]]` | The first two sentences are reported as a contradiction | 201 with one contradiction |

Sample routing: text containing *meeting / transcript / attendees / agenda* → meeting sample;
*brief / scope / requirements / deliverable* → project brief; anything else → general document
(this one has no action items, for testing the empty state).

## Running tests and lint

```bash
make test
make cov
make lint
make format
```

Tests make zero network calls (`httpx.MockTransport` for the real provider, a scripted
`FakeProvider` for the service). Optional live test against your configured provider:

```bash
RUN_LIVE_TESTS=1 LLM_PROVIDER=openai_compatible LLM_API_KEY=... LLM_MODEL=... pytest -m live
```

CI (`.github/workflows/backend.yml`) runs ruff and pytest with ≥85% coverage on Python 3.11 and
3.12, in mock mode, with no secrets.

## Design decisions and trade-offs

- **Synchronous everywhere.** `def` endpoints run in FastAPI's threadpool; simpler to test and
  reason about. Each request opens its own SQLite connection (`check_same_thread=False` because
  dependencies and endpoints may run on different pool threads).
- **No ORM.** One table; stdlib `sqlite3` with parameterized queries and WAL mode.
- **Prompt substitution uses `str.format`** on the template only, so braces in user content are
  inserted literally. `<document>`/`</document>` inside the title or text are escaped
  case-insensitively.
- **Middleware order.** CORS is outermost so that every response — including 413 and 500 —
  carries CORS headers the browser can read. Then request ID, access log (so 413s are logged
  too), body size limit, and an innermost catch-all that turns any escaped exception into the
  `INTERNAL_ERROR` envelope with the request ID still set. The spec listed request ID → body
  limit → access log → CORS; this order keeps the same guarantees and adds those two.
- **Body limit** checks `Content-Length` first and also counts streamed (chunked) bytes.
- **Normalization is lenient on cosmetics, strict on meaning.** Extra keys are ignored; a bare
  string in `action_items` becomes `{"task": ...}`; non-string list items are dropped; action
  items are de-duplicated by task. Key points and open questions are capped at 500 chars each
  (the spec gave no per-item limit).
- **Retry timing.** Backoff is `2^n` seconds (1 s, 2 s) plus 0–250 ms jitter, or the provider's
  `Retry-After` when present (no retry if > 10 s). A retry that would cross
  `LLM_TOTAL_BUDGET_SECONDS` is not started. Repair calls go through the same retry logic and
  count against the same budget.
- **Provider errors.** `APITimeoutError` is checked before `APIConnectionError` (it is a
  subclass). A 413 from the provider whose message mentions tokens maps to `CONTEXT_TOO_LONG`;
  other non-5xx statuses map to `PROVIDER_ERROR`. `retry-after-ms` is honoured too.
- **Secrets.** `LLM_API_KEY` is a `SecretStr`, registered with a redacting log formatter that also
  masks `Bearer` tokens. Document text is never logged (only its length). Per the spec, the raw
  model output (first 2,000 chars) is logged at WARNING when repair fails, to aid debugging.
- **Test hooks.** `create_app(settings, provider=None)` also accepts a provider, and
  `app.state.sleep` can replace `time.sleep` for backoff, so integration tests run instantly.
- **`METHOD_NOT_ALLOWED`** (405) was added to the error codes for wrong-method requests.
