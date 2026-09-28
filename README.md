# AI Real Estate Portfolio Analyst

A conversational AI analyst over a real-estate portfolio (WhatsApp-style chat) plus a password-protected business dashboard to inspect conversations, tool/model activity and conversations needing attention.

**Live app:** _(added at deployment)_  ·  **Admin:** `/admin`

## Documents
- [SOUL.md](SOUL.md) — agent role, tone, tools, boundaries, hand-off
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — diagram, request lifecycle, data model
- [docs/DECISIONS.md](docs/DECISIONS.md) — decision log, limitations, dependencies
- [docs/LATENCY.md](docs/LATENCY.md) — measured latency, where time goes, scaling plan
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — hosting on Render + Neon + Vercel

## Stack
FastAPI · SQLAlchemy · SQLite · httpx → OpenRouter · React (Vite). Custom tool-calling agent loop, no agent framework.

## Setup
Requires Python 3.10+ and Node.js 18+.

**Backend**
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate     Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
# edit .env: OPENROUTER_API_KEY, ADMIN_PASSWORD
python -m app.seed          # optional: the server also seeds an empty DB on first start (re-running resets properties to the CSV values)
python test_tools.py        # 10 checks, no API key needed
uvicorn app.main:app --reload --port 8000
```

**Frontend** (second terminal)
```bash
cd frontend
npm install
npm run dev
```
Chat: http://localhost:5173 · Admin: http://localhost:5173/admin · API docs: http://localhost:8000/docs

Optional terminal chat: `python chat_cli.py` (from `backend/`).

## Configuration (`backend/.env`)
| Variable | Purpose |
|---|---|
| OPENROUTER_API_KEY | model access (https://openrouter.ai/keys) |
| DEFAULT_MODEL | OpenRouter model slug, default `openrouter/free` |
| DATABASE_URL | default `sqlite:///./portfolio.db` |
| ADMIN_PASSWORD | password for `/admin` |
| FALLBACK_MODEL | optional second model tried if the primary fails twice |
| CORS_ORIGINS | allowed browser origins, default `*`; set to the frontend URL in production |

## Assumptions
- Office labels "Commercial Office" and "Office" are one category.
- Missing purchase price is unknown (NULL), never 0; no appreciation is computed.
- Yield = annual rent ÷ current estimated value (gross, current).
- Values in INR; shown as Cr/Lakh in chat.

## Project layout
```
backend/app/   agent.py  tools.py  tool_schemas.py  system_prompt.py  llm_client.py
               models.py  main.py  admin_auth.py  normalization.py  seed.py
backend/data/  users.csv  properties.csv  sample_requests.csv
frontend/src/  App.jsx (chat)  AdminApp.jsx (dashboard)  api.js
```

## External dependencies
OpenRouter (model gateway). See docs/DECISIONS.md for limitations.
