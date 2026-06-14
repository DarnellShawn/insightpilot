# 📊 InsightPilot — AI Business Analyst for E-Commerce

[![Live Demo](https://img.shields.io/badge/Live%20Demo-insightpilot--app.streamlit.app-C2552F?style=flat-square)](https://insightpilot-app.streamlit.app)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-AI-D97757?style=flat-square&logo=anthropic&logoColor=white)

> Shopify/e-commerce owners upload a transaction CSV → InsightPilot cleans it, computes
> the KPIs that matter, and Claude writes an **executive report with concrete next steps**.
> All processing is **in-memory** — no database, no data retention, GDPR-friendly by design.

**[▶ Try the live app](https://insightpilot-app.streamlit.app)** — upload the
[sample dataset](sample_data/sample_shopify_orders.csv) and generate a report in seconds.

---

## Try it

| | |
|---|---|
| 🌐 **Web app** | [insightpilot-app.streamlit.app](https://insightpilot-app.streamlit.app) |
| ⚙️ **API health** | [insightpilot-api-sp9p.onrender.com/health](https://insightpilot-api-sp9p.onrender.com/health) |
| 🖥️ **macOS desktop app** | [Releases → InsightPilot.zip](https://github.com/DarnellShawn/insightpilot/releases/latest) (Apple Silicon) |
| 📄 **Sample data** | [sample_data/sample_shopify_orders.csv](sample_data/sample_shopify_orders.csv) |

> ℹ️ The backend runs on a free tier and sleeps after inactivity — the **first request can
> take ~1 minute** to wake up (the app shows a retry button). The desktop app is an Electron
> wrapper around the web app; macOS may warn it's unsigned → right-click **Open** the first time.

<!-- SCREENSHOTS -->

## What it does

- **📥 Flexible CSV ingestion** — accepts varied Shopify-style exports; fuzzy column mapping
  resolves `Lineitem name`, `Order Number`, etc. to one canonical schema.
- **🧹 Automatic cleaning** — dedupes, coerces dates/numbers, repairs missing totals from
  `qty × price − discount`, and reports exactly what it changed.
- **📈 KPIs that matter** — net revenue, AOV, repeat-customer rate, refund rate, MoM growth,
  top products, and channel/country/weekday breakdowns.
- **🧠 AI executive report** — Claude turns the aggregated metrics into a plain-language
  report: what's working, what needs attention, and prioritized 30-day actions.
- **🔒 Privacy by design** — only **aggregated** metrics ever reach the LLM; raw rows, emails,
  and customer IDs never leave the data layer. Nothing is persisted.

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

The **privacy boundary** is a single, unit-testable function: `metrics.to_llm_payload()`
returns aggregates only — it's the one place row-level data could leak, and it can't.

## Tech stack

| Layer | Tech | Why |
|---|---|---|
| Frontend | Streamlit | Fast data-app UI, deploys free to Community Cloud |
| Backend | FastAPI + Uvicorn | Async REST, typed request/response models |
| Data | Pandas + NumPy | In-memory cleaning & KPI aggregation (`BytesIO` → DataFrame) |
| AI | Anthropic Claude (`claude-haiku-4-5`, configurable) | Streaming executive-report generation |
| Validation | Pydantic v2 | Settings + response schemas |
| Packaging | Docker | Reproducible backend image for Render |

## Repository layout

```
backend/                  FastAPI service (Docker → Render)
  app/
    main.py               App factory, CORS, router mounting
    config.py             Env-based settings (+ .env loader, key sanitization)
    api/routes.py         /health, /api/v1/analyze
    data_processing/
      loader.py           CSV parsing + flexible Shopify column mapping
      cleaning.py         Type coercion, dedupe, validation
      metrics.py          KPI computation + to_llm_payload() privacy boundary
    services/
      report_generator.py Claude executive-report generation (streaming)
    models/schemas.py     Pydantic response models
  Dockerfile · requirements.txt · .env.example
frontend/                 Streamlit app (Community Cloud)
  app.py · requirements.txt · .streamlit/config.toml
scripts/
  generate_synthetic_data.py   Realistic Shopify-like test data generator
sample_data/
  sample_shopify_orders.csv    Ready-to-upload demo dataset
render.yaml               One-click Render Blueprint
```

## Quickstart (local)

```bash
# 1. Backend — put the venv OUTSIDE iCloud-synced folders (Desktop/Documents)!
#    On macOS, a venv under an iCloud folder hangs on .so imports.
python3 -m venv ~/.venvs/insightpilot
~/.venvs/insightpilot/bin/pip install -r backend/requirements.txt

cp backend/.env.example backend/.env       # paste your ANTHROPIC_API_KEY
cd backend && ./start_dev.sh               # serves on :8000

# 2. Frontend (new terminal)
~/.venvs/insightpilot/bin/pip install -r frontend/requirements.txt
cd frontend && ~/.venvs/insightpilot/bin/streamlit run app.py
```

Open http://localhost:8501 and upload `sample_data/sample_shopify_orders.csv`.
No API key? Metrics still work — only the AI report is skipped.

## Deployment

**Backend → Render (Docker).** Push to GitHub, then in Render choose **New → Blueprint**
and select the repo. `render.yaml` configures everything; you only paste `ANTHROPIC_API_KEY`
in the dashboard.

**Frontend → Streamlit Community Cloud.** New app → main file `frontend/app.py`, then set
the app secret:

```toml
BACKEND_URL = "https://your-backend.onrender.com"
```

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness + whether report generation is configured |
| `POST` | `/api/v1/analyze` | Multipart CSV → cleaned metrics (+ AI report). `?include_report=false` for metrics-only. |

## Privacy & GDPR

- Transaction data lives only in request-scoped memory — no disk writes, no DB, no row-level logs.
- The LLM payload is restricted to aggregates by `metrics.to_llm_payload()` (unit-testable boundary).
- Set `ALLOWED_ORIGINS` to lock the API to your frontend origin in production.

## License

[MIT](LICENSE) © Darnell Himmighöfer
