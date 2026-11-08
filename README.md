# Sift: AI Document Analyzer

Sift turns unstructured text, such as meeting transcripts, project briefs, reports and notes, into a validated, structured analysis:

- a **summary** and **key points**
- **extracted entities**: people, organizations, dates, locations, technologies, money and key terms
- **action items** with owner, deadline, status, priority and an evidence quote
- **decisions**: confirmed, proposed, rejected, pending or changed
- **contradictions**, within the document and against your earlier analyses
- **risks** and **dependencies**
- **open questions**

Each user has an account, and their analyses are private to them.

```
backend/    FastAPI + SQLite REST API, LLM pipeline, auth
frontend/   React + TypeScript + Vite single-page app (landing, login, analyzer)
.github/    CI workflows for backend and frontend
```

---

## Architecture

```
 Browser (React SPA, :5173)
   │  /            landing page
   │  /login       log in / register  ──► stores bearer token in localStorage
   │  /app/*       analyzer           ──► every API call sends Authorization: Bearer <token>
   ▼
 FastAPI backend (:8000)
   middleware   CORS → request ID → access log → body-size limit → error catch-all
   api/         routes + dependency wiring (current user, user-scoped repository)
   services/    AuthService       scrypt password hashing, opaque session tokens
                AnalysisService   input checks → prompt → LLM provider (retries) →
                                  JSON extraction → schema validation (+ repair) → persist
   intelligence/ contradiction, risk and dependency pass + deterministic validation
   providers/   LLMProvider protocol: MockProvider | OpenAICompatibleProvider
   db/          sqlite3 (WAL), parameterized SQL, schema migrations
   ▼
 SQLite file (backend/data/analyses.db)   tables: users, sessions, analyses, schema_version
   ▼
 Any OpenAI-compatible LLM API (Groq by default), or the built-in mock provider
```

### Backend

- **FastAPI, synchronous endpoints.** Each request opens its own SQLite connection, and the service layer is plain Python, which keeps it simple to test.
- **Provider abstraction.** The service depends only on the `LLMProvider` protocol. `OpenAICompatibleProvider` is the only module that imports the `openai` SDK, so you can switch between Groq, OpenRouter, Gemini, xAI or a local Ollama by changing environment variables. `MockProvider` returns realistic canned output, so the app and its tests run with no API key and no network access.
- **Three-stage analysis pipeline:**
  1. **Extraction:** one LLM call produces the summary, key points, entities, action items, decisions and questions.
  2. **Intelligence:** one LLM call runs the contradiction, risk and dependency checks. Contradictions are checked within the document and against your most recent analyses. Each section is parsed on its own, so one bad section never breaks the others. If this whole stage fails, the extraction is still saved and the stage can be re-run later.
  3. **Validation:** deterministic code with no LLM call checks the output against the source text:
     - Every evidence quote must appear in the original text.
     - Owners, deadlines and entities that are not in the text are removed.
     - Dates are normalised.
     - Duplicate items are merged.
     - Each item is labelled as a fact, an inference or an assumption.
- **Robustness:**
  - **Retries:** rate limits, timeouts and outages are retried with backoff and the provider's `Retry-After` header, within a fixed total time budget.
  - **Repair:** malformed JSON gets one corrective repair call.
  - **JSON-generation errors:** when the provider reports one, the request is retried.
  - **Model output:** it never reaches the database or the client until it has passed schema validation.
- **Authentication:**
  - **Passwords:** hashed with scrypt from the standard library.
  - **Sessions:** login returns a random token. The server stores only its SHA-256 hash, and it expires after `SESSION_DAYS`.
  - **Access control:** every analysis query is limited to the current user.
- **Errors:** every error uses one JSON envelope, `{error: {code, message, retryable, request_id, details}}`, so the frontend can show precise messages.
- **Secrets:** the API key is a `SecretStr`, and logs redact keys and bearer tokens. Document text is never logged, only its length.

### Frontend

- **Stack:** React 18, React Router and TypeScript, built with Vite. Icons come from lucide-react, and headings use the Redaction 50 font.
- **Pages:**
  - **Landing:** product overview. Every call-to-action leads to the login page.
  - **Login and register:** checks input in the browser and shows backend errors beside the field they belong to. If you already have a valid session, it sends you straight to the app.
  - **Analyzer:** a header with your account and log-out button, a sidebar listing your past analyses, and the main view.
- **Analysis view:**
  - The title comes first, then a tab bar that stays visible while you scroll.
  - The tabs are Overview (summary and key points), Entities, Action items, Decisions, Contradictions, Risks, Dependencies and Open questions.
  - Tabs show item counts and flag any check that failed. They follow the accessible ARIA tabs pattern, so you can switch with the arrow keys.
- **API client:** typed `fetch` wrapper. It adds the bearer token to every request and sends you to `/login` on a 401.

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 20+

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env          # optional, see below
python -m uvicorn app.main:app --reload --port 8000
```

The API runs at http://localhost:8000. Interactive docs are at http://localhost:8000/api/docs.

With no `.env`, the backend runs in **mock mode**: realistic canned output, no API key needed.

To use a real model, such as Groq, set these in `backend/.env`:

```
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=<your key>
LLM_MODEL=openai/gpt-oss-120b
```

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env          # optional, VITE_API_URL defaults to http://localhost:8000
npm run dev
```

Open http://localhost:5173, create an account and analyse a document. The **Use sample** button fills in an example document.

### Environment variables

Every variable is optional and documented in **[backend/.env.example](backend/.env.example)** and **[frontend/.env.example](frontend/.env.example)**. The most important ones:

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | `mock` | `mock` or `openai_compatible` |
| `LLM_BASE_URL` | Groq endpoint | Any OpenAI-compatible API |
| `LLM_API_KEY` | empty | Required for `openai_compatible` |
| `LLM_MODEL` | empty | Required for `openai_compatible` |
| `LLM_ENABLE_INTELLIGENCE` | `true` | Run the contradiction, risk and dependency checks |
| `DATABASE_PATH` | `./data/analyses.db` | SQLite file location |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed browser origins |
| `SESSION_DAYS` | `30` | Login session lifetime |
| `VITE_API_URL` (frontend) | `http://localhost:8000` | Backend URL used by the browser |

Never commit `.env`. It is listed in `.gitignore`.

---

## API

All routes are under `/api`. Every route except health and auth requires `Authorization: Bearer <token>`.

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/auth/register` | Create an account and return `{token, user}` |
| POST | `/api/auth/login` | Log in and return `{token, user}` |
| GET | `/api/auth/me` | Return the current user |
| POST | `/api/auth/logout` | End the session (204) |
| POST | `/api/analyses` | Analyse `{title, text}` and return the saved record (201) |
| GET | `/api/analyses?limit=&offset=` | Your analyses, newest first |
| GET | `/api/analyses/{id}` | One analysis |
| DELETE | `/api/analyses/{id}` | Delete an analysis (204) |
| POST | `/api/analyses/{id}/intelligence` | Re-run the contradiction, risk and dependency checks |
| GET | `/api/health` | Provider, model and mock-mode status |

[backend/README.md](backend/README.md) covers the error codes, the mock trigger tokens for testing failure paths, and more design notes.

---

## Tests

```bash
# Backend: pytest, no network calls (mock transport and a scripted fake provider)
cd backend
python -m pytest
python -m pytest --cov=app --cov-fail-under=85   # with coverage
python -m ruff check . && python -m ruff format --check .

# Frontend: Vitest
cd frontend
npm test
npm run typecheck
npm run build
```

The backend tests cover:

- the API endpoints, auth (register, login, sessions and per-user isolation) and the repository
- the analysis service's retry and repair logic
- the provider's error mapping
- the validation pass

The frontend tests cover the API client (the token header and the redirect on a 401), the landing page and the analysis view (tab order, the selected tab and failed-check flags).

### Continuous integration

GitHub Actions runs on every push and pull request that touches each part of the project:

- **[.github/workflows/backend.yml](.github/workflows/backend.yml):** Ruff lint and format check, then pytest with at least 85% coverage, on Python 3.11 and 3.12, in mock mode with no secrets.
- **[.github/workflows/frontend.yml](.github/workflows/frontend.yml):** `npm ci`, type check, Vitest, then a production build on Node 20.

---

## Design notes and trade-offs

- **SQLite with no ORM.** It needs zero setup and suits a single-server proof of concept. All data access goes through one repository, so moving to PostgreSQL would only change that layer.
- **Opaque tokens, not JWTs.** Sessions can be revoked at once on logout, and there is no signing key to manage.
- **Validation after the LLM.** The model is treated as untrusted. Anything it claims has to be supported by the source text, or it is removed or labelled as an inference.
- **Known gaps:**
  - The login endpoint has no rate limiting.
  - Analyses created before accounts were added have no owner, so no one can see them.
