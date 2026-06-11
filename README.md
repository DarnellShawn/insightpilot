# InsightPilot — AI Business Analyst for E-Commerce

Production-ready MVP: Shopify/e-commerce owners upload transaction CSVs, Python/Pandas
cleans the data and computes business metrics **entirely in memory** (no database,
privacy-by-design / GDPR-friendly), and Claude generates an executive report with
actionable insights.

## Architecture

```
┌──────────────────┐         ┌───────────────────────────────────────┐
│  Streamlit       │  HTTPS  │  FastAPI Backend                      │
│  Frontend        ├────────►│  ┌─────────────┐  ┌────────────────┐  │
│  (Community      │  CSV    │  │ Pandas      │  │ Claude API     │  │
│   Cloud)         │◄────────┤  │ clean +     ├─►│ executive      │  │
│                  │ metrics │  │ metrics     │  │ report         │  │
└──────────────────┘ +report │  └─────────────┘  └────────────────┘  │
                             │  In-memory only — nothing persisted   │
                             └───────────────────────────────────────┘
                                  Docker → Render
```

- **No database.** Uploaded CSVs are processed in memory (`BytesIO` → DataFrame) and
  discarded when the request completes.
- **No PII reaches the LLM.** Only aggregated metrics (totals, rates, top-N lists) are
  sent to Claude — never raw rows, emails, or customer identifiers.
- **Strict separation.** `backend/` and `frontend/` are independent deployables with
  their own `requirements.txt`.

## Repository Layout

```
backend/                  FastAPI service (Docker → Render)
  app/
    main.py               App factory, CORS, router mounting
    config.py             Env-based settings
    api/routes.py         /health, /api/v1/analyze
    data_processing/
      loader.py           CSV parsing + flexible Shopify column mapping
      cleaning.py         Type coercion, dedupe, validation
      metrics.py          KPI computation (revenue, AOV, retention, ...)
    services/
      report_generator.py Claude executive-report generation
    models/schemas.py     Pydantic response models
  requirements.txt
  Dockerfile
  .env.example
frontend/                 Streamlit app (Streamlit Community Cloud)
  app.py
  requirements.txt
  .streamlit/config.toml
scripts/
  generate_synthetic_data.py   Realistic Shopify-like test data
data/                     Generated sample CSVs (git-ignored, for local testing)
```

## Quickstart (local)

```bash
# 1. Generate test data
python3 scripts/generate_synthetic_data.py --rows 5000 --out data/shopify_orders.csv

# 2. Backend — put the venv OUTSIDE iCloud-synced folders (e.g. ~/Desktop)!
#    On macOS, a venv under Desktop/Documents hangs on .so imports (iCloud sync).
python3 -m venv ~/.venvs/insightpilot
~/.venvs/insightpilot/bin/pip install -r backend/requirements.txt

cp backend/.env.example backend/.env       # then paste your ANTHROPIC_API_KEY
cd backend && ./start_dev.sh               # or: ~/.venvs/insightpilot/bin/uvicorn app.main:app --reload --port 8000

# 3. Frontend (new terminal)
~/.venvs/insightpilot/bin/pip install -r frontend/requirements.txt
cd frontend && ~/.venvs/insightpilot/bin/streamlit run app.py
```

Open http://localhost:8501, upload `data/shopify_orders.csv`, and generate a report.

## Deployment

### Backend → Render (Docker)

**Option A — Blueprint (recommended):** push this repo to GitHub, then in Render choose
**New → Blueprint** and select the repo. `render.yaml` configures everything; you only
paste `ANTHROPIC_API_KEY` in the dashboard.

**Option B — manual:**
1. Push this repo to GitHub.
2. Render → New → Web Service → select repo, set **Root Directory** to `backend/`.
   Render auto-detects the `Dockerfile`.
3. Environment variables: `ANTHROPIC_API_KEY`, optionally `REPORT_MODEL`,
   `ALLOWED_ORIGINS` (set to your Streamlit app URL).

### Frontend → Streamlit Community Cloud

1. New app → select repo → main file `frontend/app.py`.
2. App secrets:
   ```toml
   BACKEND_URL = "https://your-backend.onrender.com"
   ```

## API

| Method | Path              | Description                                              |
|--------|-------------------|----------------------------------------------------------|
| GET    | `/health`         | Liveness + whether report generation is configured       |
| POST   | `/api/v1/analyze` | Multipart CSV upload → cleaned metrics (+ AI report). Query param `include_report=false` for metrics-only. |

## Privacy & GDPR Notes

- Transaction data lives only in request-scoped memory; no disk writes, no DB, no logs of row-level data.
- The LLM payload is restricted to aggregates; a unit-testable boundary
  (`metrics.to_llm_payload`) enforces this.
- Configure `ALLOWED_ORIGINS` to lock the API to your frontend origin in production.
