# Deployment

Vercel (React frontend) -> Render (FastAPI backend) -> Neon (Postgres). OpenRouter is the model gateway.

## Environment variables
**Render (backend)**
| Variable | Value |
|---|---|
| PYTHON_VERSION | `3.12.3` (the pinned packages are not built for the newest Python) |
| OPENROUTER_API_KEY | your key |
| DEFAULT_MODEL | `openrouter/free`, or a paid model slug |
| ADMIN_PASSWORD | choose a strong password; share it with reviewers through the submission form, not the repo |
| DATABASE_URL | the Neon connection string |
| CORS_ORIGINS | the Vercel URL, e.g. `https://your-app.vercel.app` (no trailing slash) |
| FALLBACK_MODEL | optional |

Render settings: root directory `backend`, build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check path `/health`.

**Vercel (frontend):** root directory `frontend`, variable `VITE_API_BASE_URL` = the Render URL (no trailing slash). `vercel.json` rewrites every path to `index.html` so `/admin` works on a direct visit.

## Things to know
- The dataset is loaded automatically the first time the server starts against an empty database.
- Free Render services sleep after a period of inactivity; the first request afterwards can take around a minute. Open the app before a demo.
- OpenRouter `:free` models have a daily request cap (see DECISIONS.md, known limitations).
- Never commit `.env`. If a key is ever pushed, rotate it.
